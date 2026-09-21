import argparse
import json
import random
import statistics
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, func, text
from sqlalchemy.orm import sessionmaker, joinedload

try:
    from config import DATABASE_URL
except ImportError:
    print("ОШИБКА: не найден config.py с переменной DATABASE_URL.",
          file=sys.stderr)
    sys.exit(1)

from models import (
    Base, Family, Genus, Species, Specimen, Trait, Measurement,
)


DEFAULT_RUNS = 30
WARMUP_RUNS = 3
FILTER_LIMIT = 100
IMPORT_BATCH_SIZE = 1000
IMPORT_CHUNK_SIZE = 500 

SEED_FAMILIES = 20
SEED_GENERA_PER_FAMILY = 5
SEED_SPECIES_PER_GENUS = 10
SEED_SPECIMENS = 10000
SEED_TRAITS = 50
SEED_MEASUREMENTS_PER_SPECIMEN = 10


def measure(func, n_runs: int, warmup: int = WARMUP_RUNS) -> dict:
    for _ in range(warmup):
        try:
            func()
        except Exception as e:
            return {"error": f"{type(e).__name__}: {e}"}

    times = []
    for _ in range(n_runs):
        t0 = time.perf_counter()
        try:
            func()
        except Exception as e:
            return {"error": f"{type(e).__name__}: {e}"}
        times.append(time.perf_counter() - t0)

    times.sort()
    n = len(times)
    return {
        "n": n,
        "mean": statistics.mean(times),
        "sd": statistics.stdev(times) if n > 1 else 0.0,
        "min": min(times),
        "max": max(times),
        "p50": times[n // 2],
        "p95": times[int(0.95 * n) - 1] if n > 1 else times[0],
    }


def detect_db_kind(url: str) -> str:
    if url.startswith("sqlite"):
        return "SQLite"
    if url.startswith("postgresql") or url.startswith("postgres"):
        return "PostgreSQL"
    return "Unknown"


def get_first_family(session):
    row = session.query(Family).order_by(Family.id).first()
    return row.name if row else None


def get_first_trait(session):
    row = session.query(Trait).order_by(Trait.id).first()
    return row.name if row else None


def seed_database(session,
                  n_families=SEED_FAMILIES,
                  n_genera_per_family=SEED_GENERA_PER_FAMILY,
                  n_species_per_genus=SEED_SPECIES_PER_GENUS,
                  n_specimens=SEED_SPECIMENS,
                  n_traits=SEED_TRAITS,
                  n_measurements_per_specimen=SEED_MEASUREMENTS_PER_SPECIMEN):
 
    print("\n" + "=" * 70)
    print("Генерация синтетических данных")
    print("=" * 70)

    print(f"[1/5] Семейства: {n_families} ...")
    families = [Family(name=f"Family_{i:03d}") for i in range(n_families)]
    session.add_all(families)
    session.flush()

    print(f"[2/5] Роды: {n_families * n_genera_per_family} ...")
    genera = []
    for fam in families:
        for j in range(n_genera_per_family):
            genera.append(Genus(name=f"Genus_{fam.id:03d}_{j:02d}",
                                family_id=fam.id))
    session.add_all(genera)
    session.flush()

    total_species = len(genera) * n_species_per_genus
    print(f"[3/5] Виды: {total_species} ...")
    species = []
    for gen in genera:
        for k in range(n_species_per_genus):
            species.append(Species(name=f"species_{gen.id:04d}_{k:02d}",
                                   genus_id=gen.id))
    session.add_all(species)
    session.flush()

    print(f"[4/5] Признаки: {n_traits} ...")
    traits = [Trait(name=f"Trait_{i:03d}", unit="mm", data_type="float")
              for i in range(n_traits)]
    session.add_all(traits)
    session.flush()

    print(f"[5/5] Образцы: {n_specimens} (батчами по 1000) ...")
    all_specimens = []
    batch_size = 1000

    for batch_start in range(0, n_specimens, batch_size):
        batch_end = min(batch_start + batch_size, n_specimens)
        batch = []
        for i in range(batch_start, batch_end):
            sp = random.choice(species)
            batch.append(Specimen(
                species_id=sp.id,
                collector=f"Collector_{i % 50:02d}",
                collection_date=(datetime(2020, 1, 1) +
                                 timedelta(days=random.randint(0, 2000))
                                 ).strftime("%Y-%m-%d"),
                location=f"Locality_{i % 100:03d}",
            ))
        session.add_all(batch)
        session.flush()
        all_specimens.extend(batch)
        print(f"      Образцы: {batch_end}/{n_specimens}")

    total_measurements = n_specimens * n_measurements_per_specimen
    print(f"      Измерения: {total_measurements} (ожидаемое число) ...")
    done = 0
    for spec in all_specimens:
        chosen = random.sample(traits, n_measurements_per_specimen)
        measurements = [
            Measurement(specimen_id=spec.id, trait_id=tr.id,
                        value=str(round(random.uniform(1, 100), 2)))
            for tr in chosen
        ]
        session.add_all(measurements)
        done += len(measurements)
        if done % 10000 == 0 or done == total_measurements:
            session.flush()
            print(f"      Измерения: {done}/{total_measurements}")

    session.commit()

    print("=" * 70)
    print(f"Готово: {n_families} семейств, "
          f"{len(genera)} родов, "
          f"{len(species)} видов, "
          f"{len(all_specimens)} образцов, "
          f"{n_traits} признаков, "
          f"{done} измерений.")
    print("=" * 70 + "\n")


def make_session_factory():
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
    return sessionmaker(bind=engine, expire_on_commit=False)


def scenario_filter_by_family(session_factory, family_name):
    def run():
        session = session_factory()
        try:
            (session.query(Specimen)
             .join(Species).join(Genus).join(Family)
             .filter(Family.name == family_name)
             .options(
                 joinedload(Specimen.species)
                 .joinedload(Species.genus)
                 .joinedload(Genus.family),
             )
             .limit(FILTER_LIMIT)
             .all())
        finally:
            session.close()
    return run


def scenario_filter_by_trait(session_factory, trait_name, threshold="50"):
    def run():
        session = session_factory()
        try:
            subq = (session.query(Measurement.specimen_id)
                    .join(Trait)
                    .filter(Trait.name == trait_name)
                    .filter(Measurement.value > threshold))
            (session.query(Specimen)
             .filter(Specimen.id.in_(subq))
             .limit(FILTER_LIMIT)
             .all())
        finally:
            session.close()
    return run


def scenario_boxplot_data(session_factory, trait_name):
    def run():
        session = session_factory()
        try:
            (session.query(Measurement)
             .join(Trait)
             .filter(Trait.name == trait_name)
             .all())
        finally:
            session.close()
    return run


def scenario_export_all(session_factory):
    def run():
        session = session_factory()
        try:
            specimens = (session.query(Specimen)
                         .options(
                             joinedload(Specimen.species)
                             .joinedload(Species.genus)
                             .joinedload(Genus.family),
                             joinedload(Specimen.measurements)
                             .joinedload(Measurement.trait),
                         )
                         .all())
            data = []
            for s in specimens:
                row = {
                    "ID": s.id,
                    "Вид": s.species.name if s.species else None,
                    "Род": (s.species.genus.name
                            if s.species and s.species.genus else None),
                    "Семейство": (s.species.genus.family.name
                                  if s.species and s.species.genus
                                  and s.species.genus.family else None),
                }
                for m in s.measurements:
                    row[m.trait.name] = m.value
                data.append(row)
            pd.DataFrame(data)
        finally:
            session.close()
    return run


def scenario_import(session_factory, batch_size, chunk_size=IMPORT_CHUNK_SIZE):

    def run():
        session = session_factory()
        try:
            specimen_ids = [row[0] for row in
                            session.query(Specimen.id).limit(100).all()]
            trait_ids = [row[0] for row in
                         session.query(Trait.id).limit(10).all()]
            if not specimen_ids or not trait_ids:
                raise RuntimeError("Нет данных для теста импорта")

            rows = [
                {
                    "specimen_id": random.choice(specimen_ids),
                    "trait_id": random.choice(trait_ids),
                    "value": str(round(random.uniform(1, 100), 2)),
                }
                for _ in range(batch_size)
            ]

            for i in range(0, len(rows), chunk_size):
                chunk = rows[i:i + chunk_size]
                session.execute(
                    text(
                        "INSERT INTO measurements "
                        "(specimen_id, trait_id, value) "
                        "VALUES (:specimen_id, :trait_id, :value)"
                    ),
                    chunk,
                )

            session.rollback()
        finally:
            session.close()

    return run

def main():
    parser = argparse.ArgumentParser(description="Бенчмарк БД")
    parser.add_argument("--runs", type=int, default=DEFAULT_RUNS,
                        help="Число повторов на сценарий")
    parser.add_argument("--allow-write", action="store_true",
                        help="Разрешить тест импорта (с откатом транзакции)")
    parser.add_argument("--seed", action="store_true",
                        help="Сгенерировать синтетические данные перед тестом")
    parser.add_argument("--seed-specimens", type=int, default=SEED_SPECIMENS,
                        help="Число образцов для генерации")
    parser.add_argument("--seed-families", type=int, default=SEED_FAMILIES)
    parser.add_argument("--seed-traits", type=int, default=SEED_TRAITS)
    parser.add_argument("--out", type=str, default="benchmark",
                        help="Префикс для файлов с результатами")
    args = parser.parse_args()

    session_factory = make_session_factory()
    session = session_factory()

    try:
        db_kind = detect_db_kind(DATABASE_URL)

        if args.seed:
            confirm = input(
                f"\nВы собираетесь добавить "
                f"{args.seed_specimens} образцов в базу {db_kind}.\n"
                f"Продолжить? [y/N]: "
            ).strip().lower()
            if confirm != "y":
                print("Отменено.")
                return

            seed_database(session,
                          n_families=args.seed_families,
                          n_specimens=args.seed_specimens,
                          n_traits=args.seed_traits)

        n_families = session.query(func.count(Family.id)).scalar() or 0
        n_genera = session.query(func.count(Genus.id)).scalar() or 0
        n_species = session.query(func.count(Species.id)).scalar() or 0
        n_specimens = session.query(func.count(Specimen.id)).scalar() or 0
        n_traits = session.query(func.count(Trait.id)).scalar() or 0
        n_measurements = session.query(func.count(Measurement.id)).scalar() or 0

        print("=" * 70)
        print("Бенчмарк базы данных")
        print(f"Дата: {datetime.now().isoformat(timespec='seconds')}")
        print(f"СУБД: {db_kind}")
        print(f"Число повторов на сценарий: {args.runs}")
        print("=" * 70)
        print(f"Семейств:            {n_families}")
        print(f"Родов:               {n_genera}")
        print(f"Видов:               {n_species}")
        print(f"Образцов:            {n_specimens}")
        print(f"Признаков:           {n_traits}")
        print(f"Измерений:           {n_measurements}")
        print("=" * 70)

        if n_specimens == 0:
            print("\nNone")

        family_name = get_first_family(session)
        trait_name = get_first_trait(session)

        results = {}

        if family_name:
            print(f"\n[1/5] Фильтрация по семейству «{family_name}» ...")
            r = measure(scenario_filter_by_family(session_factory, family_name),
                        args.runs)
            results["filter_by_family"] = r
            if "error" not in r:
                print(f"      mean = {r['mean']:.4f} с, "
                      f"SD = {r['sd']:.4f}, p95 = {r['p95']:.4f} с")
            else:
                print(f"      ОШИБКА: {r['error']}")

        if trait_name:
            print(f"\n[2/5] Фильтрация по признаку «{trait_name}» ...")
            r = measure(scenario_filter_by_trait(session_factory, trait_name),
                        args.runs)
            results["filter_by_trait"] = r
            if "error" not in r:
                print(f"      mean = {r['mean']:.4f} с, "
                      f"SD = {r['sd']:.4f}, p95 = {r['p95']:.4f} с")
            else:
                print(f"      ОШИБКА: {r['error']}")

        if trait_name:
            print(f"\n[3/5] Подготовка данных для boxplot «{trait_name}» ...")
            r = measure(scenario_boxplot_data(session_factory, trait_name),
                        args.runs)
            results["boxplot_data"] = r
            if "error" not in r:
                print(f"      mean = {r['mean']:.4f} с, "
                      f"SD = {r['sd']:.4f}, p95 = {r['p95']:.4f} с")
            else:
                print(f"      ОШИБКА: {r['error']}")

        print(f"\n[4/5] Экспорт всех образцов с измерениями ...")
        r = measure(scenario_export_all(session_factory), args.runs)
        results["export_all"] = r
        if "error" not in r:
            print(f"      mean = {r['mean']:.4f} с, "
                  f"SD = {r['sd']:.4f}, p95 = {r['p95']:.4f} с")
        else:
            print(f"      ОШИБКА: {r['error']}")

        if args.allow_write and trait_name:
            print(f"\n[5/5] Импорт {IMPORT_BATCH_SIZE} строк")
            n_import_runs = max(5, args.runs // 3)
            r = measure(
                scenario_import(session_factory, IMPORT_BATCH_SIZE),
                n_import_runs,
            )
            results["import_batch"] = r
            if "error" not in r:
                print(f"      mean = {r['mean']:.4f} с, "
                      f"SD = {r['sd']:.4f}, p95 = {r['p95']:.4f} с")
            else:
                print(f"      ОШИБКА: {r['error']}")
        else:
            print("\n[5/5] Импорт: пропущен "
                  "(запустите с --allow-write)")

    finally:
        session.close()

    out_prefix = Path(args.out)

    rows_out = []
    for op, r in results.items():
        if "error" in r:
            rows_out.append({"operation": op, "error": r["error"]})
            continue
        rows_out.append({
            "operation": op,
            "n": r["n"],
            "mean_s": round(r["mean"], 4),
            "sd_s": round(r["sd"], 4),
            "min_s": round(r["min"], 4),
            "max_s": round(r["max"], 4),
            "p50_s": round(r["p50"], 4),
            "p95_s": round(r["p95"], 4),
        })
    df = pd.DataFrame(rows_out)
    df.to_csv(f"{out_prefix}_results.csv", index=False)

    with open(f"{out_prefix}_results.json", "w", encoding="utf-8") as f:
        json.dump({
            "datetime": datetime.now().isoformat(timespec="seconds"),
            "db_kind": db_kind,
            "counts": {
                "families": n_families,
                "genera": n_genera,
                "species": n_species,
                "specimens": n_specimens,
                "traits": n_traits,
                "measurements": n_measurements,
            },
            "results": results,
        }, f, ensure_ascii=False, indent=2)

    with open(f"{out_prefix}_summary.txt", "w", encoding="utf-8") as f:
        f.write("=" * 70 + "\n")
        f.write("Сводка результатов нагрузочного тестирования\n")
        f.write(f"Дата: {datetime.now().isoformat(timespec='seconds')}\n")
        f.write(f"СУБД: {db_kind}\n")
        f.write(f"Объём данных: {n_specimens} образцов, "
                f"{n_measurements} измерений\n")
        f.write("=" * 70 + "\n\n")
        f.write(f"{'Операция':<30} {'mean ± SD (с)':<20} {'p95 (с)':<10}\n")
        f.write("-" * 62 + "\n")

        op_names = {
            "filter_by_family": "Фильтрация по семейству",
            "filter_by_trait": "Фильтрация по признаку",
            "boxplot_data": "Подготовка boxplot",
            "export_all": "Экспорт всех образцов",
            "import_batch": "Импорт 1000 строк",
        }
        for key, r in results.items():
            if "error" in r:
                f.write(f"{op_names.get(key, key):<30} ОШИБКА: {r['error']}\n")
                continue
            name = op_names.get(key, key)
            mean_sd = f"{r['mean']:.2f} ± {r['sd']:.2f}"
            f.write(f"{name:<30} {mean_sd:<20} {r['p95']:<10.2f}\n")

    print("\n" + "=" * 70)
    print("Результаты сохранены:")
    print(f"  {out_prefix}_results.csv")
    print(f"  {out_prefix}_results.json")
    print(f"  {out_prefix}_summary.txt")
    print("=" * 70)

if __name__ == "__main__":
    main()