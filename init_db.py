# init_db.py
from models import Session, Family, Genus, Species, Trait

session = Session()

# 1. Добавляем семейства
families_data = ["Rosaceae", "Asteraceae", "Fabaceae", "Brassicaceae"]
for fname in families_data:
    family = session.query(Family).filter_by(name=fname).first()
    if not family:
        family = Family(name=fname)
        session.add(family)
        print(f"Добавлено семейство: {fname}")

session.commit()  # сохраняем семейства, чтобы получить их id

# 2. Добавляем роды для этих семейств
genera_data = {
    "Rosaceae": ["Rosa", "Malus", "Prunus"],
    "Asteraceae": ["Taraxacum", "Helianthus", "Artemisia"],
    "Fabaceae": ["Trifolium", "Lupinus", "Vicia"],
    "Brassicaceae": ["Brassica", "Arabidopsis"]
}
for family_name, genus_list in genera_data.items():
    family = session.query(Family).filter_by(name=family_name).first()
    if family:
        for gname in genus_list:
            genus = session.query(Genus).filter_by(name=gname, family_id=family.id).first()
            if not genus:
                genus = Genus(name=gname, family_id=family.id)
                session.add(genus)
                print(f"  Добавлен род: {gname} (сем. {family_name})")
session.commit()

# 3. Добавляем виды для некоторых родов
species_data = {
    "Rosa": ["canina", "rugosa", "damascena"],
    "Taraxacum": ["officinale", "erythrospermum"],
    "Trifolium": ["pratense", "repens"],
    "Brassica": ["oleracea", "napus"]
}
for genus_name, species_list in species_data.items():
    genus = session.query(Genus).filter_by(name=genus_name).first()
    if genus:
        for spname in species_list:
            species = session.query(Species).filter_by(name=spname, genus_id=genus.id).first()
            if not species:
                species = Species(name=spname, genus_id=genus.id)
                session.add(species)
                print(f"    Добавлен вид: {spname} (род {genus_name})")
session.commit()

# 4. Добавляем признаки (морфологические параметры)
traits_data = [
    {"name": "Длина листа", "unit": "мм", "data_type": "float"},
    {"name": "Ширина лепестка", "unit": "мм", "data_type": "float"},
    {"name": "Высота растения", "unit": "см", "data_type": "float"},
    {"name": "Окраска цветка", "unit": "", "data_type": "category"},
    {"name": "Тип опушения", "unit": "", "data_type": "category"},
]
for t in traits_data:
    trait = session.query(Trait).filter_by(name=t["name"]).first()
    if not trait:
        trait = Trait(name=t["name"], unit=t["unit"], data_type=t["data_type"])
        session.add(trait)
        print(f"Добавлен признак: {t['name']}")
session.commit()

print("✅ Инициализация базы данных завершена!")
session.close()