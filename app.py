# app.py
import streamlit as st
import pandas as pd
import plotly.express as px
import os
from datetime import datetime
from models import Session, Family, Genus, Species, Specimen, Trait, Measurement
from sqlalchemy.orm import joinedload
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import or_
from PIL import Image
import io
import openpyxl

st.set_page_config(page_title="база данных", layout="wide")
st.title("База данных Лаборатории флоры и систематики растений")

# ---------- НАСТРОЙКА ПАПКИ ДЛЯ ИЗОБРАЖЕНИЙ ----------
IMAGE_UPLOAD_DIR = "uploads"
if not os.path.exists(IMAGE_UPLOAD_DIR):
    os.makedirs(IMAGE_UPLOAD_DIR)

# ---------- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ----------
def get_families():
    session = Session()
    try:
        return session.query(Family).order_by(Family.name).all()
    finally:
        session.close()

def get_genera_by_family(family_name):
    session = Session()
    try:
        family = session.query(Family).filter(Family.name == family_name).first()
        if family:
            return family.genera
        return []
    finally:
        session.close()

def get_species_by_genus(genus_name, family_id=None):
    session = Session()
    try:
        query = session.query(Genus).filter(Genus.name == genus_name)
        if family_id:
            query = query.filter(Genus.family_id == family_id)
        genus = query.first()
        if genus:
            return genus.species
        return []
    finally:
        session.close()

def get_traits():
    session = Session()
    try:
        return session.query(Trait).order_by(Trait.name).all()
    finally:
        session.close()

def add_family(name):
    session = Session()
    try:
        existing = session.query(Family).filter(Family.name == name).first()
        if existing:
            return False, "Семейство уже существует"
        family = Family(name=name)
        session.add(family)
        session.commit()
        return True, "Семейство добавлено"
    except Exception as e:
        session.rollback()
        return False, str(e)
    finally:
        session.close()

def add_genus(name, family_name):
    session = Session()
    try:
        family = session.query(Family).filter(Family.name == family_name).first()
        if not family:
            return False, "Семейство не найдено"
        existing = session.query(Genus).filter(Genus.name == name, Genus.family_id == family.id).first()
        if existing:
            return False, "Род уже существует в этом семействе"
        genus = Genus(name=name, family_id=family.id)
        session.add(genus)
        session.commit()
        return True, "Род добавлен"
    except Exception as e:
        session.rollback()
        return False, str(e)
    finally:
        session.close()

def add_trait(name, unit, data_type):
    session = Session()
    try:
        existing = session.query(Trait).filter(Trait.name == name).first()
        if existing:
            return False, "Признак уже существует"
        trait = Trait(name=name, unit=unit, data_type=data_type)
        session.add(trait)
        session.commit()
        return True, "Признак добавлен"
    except Exception as e:
        session.rollback()
        return False, str(e)
    finally:
        session.close()

def add_specimen(family_name, genus_name, species_name, new_species, 
                 collector, collection_date, location, trait_values, image_file=None):
    session = Session()
    try:
        session.begin()
        family = session.query(Family).filter(Family.name == family_name).first()
        if not family:
            family = Family(name=family_name)
            session.add(family)
            session.flush()
        genus = session.query(Genus).filter(Genus.name == genus_name, Genus.family_id == family.id).first()
        if not genus:
            genus = Genus(name=genus_name, family_id=family.id)
            session.add(genus)
            session.flush()
        if new_species:
            species_obj = Species(name=new_species, genus_id=genus.id)
            session.add(species_obj)
            session.flush()
        else:
            species_obj = session.query(Species).filter(
                Species.name == species_name, 
                Species.genus_id == genus.id
            ).first()
            if not species_obj:
                raise ValueError(f"Вид '{species_name}' не найден в роду '{genus_name}'")
        
        image_path = None
        if image_file is not None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            ext = image_file.name.split('.')[-1]
            filename = f"{timestamp}_{species_obj.name}.{ext}"
            filepath = os.path.join(IMAGE_UPLOAD_DIR, filename)
            with open(filepath, "wb") as f:
                f.write(image_file.getbuffer())
            image_path = filepath
        
        specimen = Specimen(
            species_id=species_obj.id,
            collector=collector,
            collection_date=collection_date,
            location=location,
            image_path=image_path
        )
        session.add(specimen)
        session.flush()
        
        for trait_id, val in trait_values.items():
            if val and val.strip():
                meas = Measurement(specimen_id=specimen.id, trait_id=trait_id, value=val.strip())
                session.add(meas)
        
        session.commit()
        return True, "Образец успешно добавлен"
    except (ValueError, SQLAlchemyError) as e:
        session.rollback()
        return False, str(e)
    except Exception as e:
        session.rollback()
        return False, f"Неизвестная ошибка: {e}"
    finally:
        session.close()

def get_filtered_specimens(family_name=None, genus_name=None, location=None, collector=None, 
                           date_from=None, date_to=None, has_image=None, search_text=None, limit=None):
    session = Session()
    try:
        query = (session.query(Specimen)
                 .options(
                     joinedload(Specimen.species)
                     .joinedload(Species.genus)
                     .joinedload(Genus.family),
                     joinedload(Specimen.measurements)
                     .joinedload(Measurement.trait)
                 ))
        if family_name and family_name != "Все":
            query = query.join(Specimen.species).join(Species.genus).join(Genus.family).filter(Family.name == family_name)
        if genus_name and genus_name != "Все":
            query = query.join(Specimen.species).join(Species.genus).filter(Genus.name == genus_name)
        if location:
            query = query.filter(Specimen.location.ilike(f"%{location}%"))
        if collector:
            query = query.filter(Specimen.collector.ilike(f"%{collector}%"))
        if date_from:
            query = query.filter(Specimen.collection_date >= date_from)
        if date_to:
            query = query.filter(Specimen.collection_date <= date_to)
        if has_image is True:
            query = query.filter(Specimen.image_path.isnot(None))
        elif has_image is False:
            query = query.filter(Specimen.image_path.is_(None))
        if search_text:
            search = f"%{search_text}%"
            query = query.filter(
                or_(
                    Specimen.id.cast(str).ilike(search),
                    Specimen.collector.ilike(search),
                    Specimen.location.ilike(search),
                    Specimen.species.has(Species.name.ilike(search)),
                    Specimen.species.has(Genus.name.ilike(search)),
                    Specimen.species.has(Genus.has(Family.name.ilike(search)))
                )
            )
        if limit:
            query = query.limit(limit)
        return query.all()
    finally:
        session.close()

def import_from_excel(df):
    session = Session()
    try:
        session.begin()
        added = 0
        errors = []
        existing_traits = {t.name: t for t in session.query(Trait).all()}
        
        for idx, row in df.iterrows():
            try:
                family_name = str(row.get("Семейство", ""))
                genus_name = str(row.get("Род", ""))
                species_name = str(row.get("Вид", ""))
                if not family_name or not genus_name or not species_name:
                    errors.append(f"Строка {idx+2}: пропущено семейство, род или вид")
                    continue
                
                family = session.query(Family).filter(Family.name == family_name).first()
                if not family:
                    family = Family(name=family_name)
                    session.add(family)
                    session.flush()
                
                genus = session.query(Genus).filter(Genus.name == genus_name, Genus.family_id == family.id).first()
                if not genus:
                    genus = Genus(name=genus_name, family_id=family.id)
                    session.add(genus)
                    session.flush()
                
                species = session.query(Species).filter(Species.name == species_name, Species.genus_id == genus.id).first()
                if not species:
                    species = Species(name=species_name, genus_id=genus.id)
                    session.add(species)
                    session.flush()
                
                collector = row.get("Коллектор", "")
                collection_date = row.get("Дата_сбора", "")
                location = row.get("Место_сбора", "")
                specimen = Specimen(
                    species_id=species.id,
                    collector=collector,
                    collection_date=collection_date,
                    location=location
                )
                session.add(specimen)
                session.flush()
                
                for col in df.columns:
                    if col in ["Семейство", "Род", "Вид", "Коллектор", "Дата_сбора", "Место_сбора"]:
                        continue
                    val = row.get(col)
                    if pd.isna(val) or val == "":
                        continue
                    trait = existing_traits.get(col)
                    if not trait:
                        trait = Trait(name=col, unit="", data_type="float")
                        session.add(trait)
                        session.flush()
                        existing_traits[col] = trait
                    meas = Measurement(specimen_id=specimen.id, trait_id=trait.id, value=str(val))
                    session.add(meas)
                
                added += 1
            except Exception as e:
                errors.append(f"Строка {idx+2}: {str(e)}")
        
        session.commit()
        return added, errors
    except Exception as e:
        session.rollback()
        return 0, [str(e)]
    finally:
        session.close()

# ===================== БОКОВАЯ ПАНЕЛЬ (фильтры и экспорт) =====================
st.sidebar.header("Фильтры и поиск")

# Основные таксономические фильтры
families = get_families()
family_choices = ["Все"] + [f.name for f in families]
selected_family = st.sidebar.selectbox("Семейство", family_choices)

if selected_family != "Все":
    genera = get_genera_by_family(selected_family)
else:
    session = Session()
    try:
        genera = session.query(Genus).order_by(Genus.name).all()
    finally:
        session.close()
genus_choices = ["Все"] + [g.name for g in genera]
selected_genus = st.sidebar.selectbox("Род", genus_choices)

# Глобальный текстовый поиск
search_text = st.sidebar.text_input("Поиск по тексту (ID, вид, род, семейство, коллектор, локалитет)")

# Дополнительные фильтры
st.sidebar.subheader("Дополнительные фильтры")
location_filter = st.sidebar.text_input("Локалитет (поиск по части)")
collector_filter = st.sidebar.text_input("Коллектор (поиск по части)")
date_from = st.sidebar.text_input("Дата сбора (от, ГГГГ-ММ-ДД)")
date_to = st.sidebar.text_input("Дата сбора (до, ГГГГ-ММ-ДД)")
has_image = st.sidebar.selectbox("Наличие изображения", ["Все", "Есть", "Нет"])
if has_image == "Есть":
    has_image_flag = True
elif has_image == "Нет":
    has_image_flag = False
else:
    has_image_flag = None

# Кнопка "Применить фильтры" (для явного обновления)
if st.sidebar.button("Применить фильтры"):
    st.rerun()

# Количество записей для просмотра
limit = st.sidebar.slider("Количество записей для просмотра (TOP-N)", 10, 500, 100, step=10)

# Кнопка экспорта всех отфильтрованных данных
st.sidebar.markdown("---")
st.sidebar.subheader("Экспорт данных")
if st.sidebar.button("Экспортировать все отфильтрованные записи (CSV)"):
    with st.spinner("Подготовка данных..."):
        all_specimens = get_filtered_specimens(
            family_name=selected_family,
            genus_name=selected_genus,
            location=location_filter,
            collector=collector_filter,
            date_from=date_from if date_from else None,
            date_to=date_to if date_to else None,
            has_image=has_image_flag,
            search_text=search_text if search_text else None,
            limit=None
        )
        if not all_specimens:
            st.sidebar.warning("Нет данных для экспорта.")
        else:
            data = []
            for s in all_specimens:
                measurements = {m.trait.name: m.value for m in s.measurements}
                row = {
                    "ID": s.id,
                    "Вид": s.species.name,
                    "Род": s.species.genus.name,
                    "Семейство": s.species.genus.family.name,
                    "Коллектор": s.collector,
                    "Дата сбора": s.collection_date,
                    "Место сбора": s.location,
                    **measurements
                }
                data.append(row)
            df_export = pd.DataFrame(data)
            csv = df_export.to_csv(index=False).encode('utf-8')
            st.sidebar.download_button(
                label="Скачать CSV",
                data=csv,
                file_name=f"образцы_фильтр_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv"
            )
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df_export.to_excel(writer, index=False, sheet_name='Образцы')
            excel_data = output.getvalue()
            st.sidebar.download_button(
                label="Скачать Excel",
                data=excel_data,
                file_name=f"образцы_фильтр_{datetime.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

# ===================== ТАБЫ =====================
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "Добавление данных", 
    "Добавить таксон/признак", 
    "Просмотр", 
    "Визуализация",
    "Импорт из Excel"
])

# ---------- Вкладка 1: Добавление образца ----------
with tab1:
    st.header("Добавление нового образца")
    with st.form("add_form"):
        family_names = [f.name for f in get_families()]
        family_option = st.selectbox(
            "Семейство", 
            ["Выберите или введите новое..."] + family_names
        )
        if family_option == "Выберите или введите новое...":
            family_name = st.text_input("Введите новое семейство")
        else:
            family_name = family_option
        
        if family_name and family_name not in ["Выберите или введите новое...", ""]:
            genera_list = get_genera_by_family(family_name) if family_name in family_names else []
            genus_names = [g.name for g in genera_list]
        else:
            genus_names = []
        
        genus_option = st.selectbox(
            "Род", 
            ["Выберите или введите новый..."] + genus_names
        )
        if genus_option == "Выберите или введите новый...":
            genus_name = st.text_input("Введите новый род")
        else:
            genus_name = genus_option
        
        if genus_name and genus_name not in ["Выберите или введите новый...", ""]:
            if family_name in family_names:
                family_obj = next((f for f in get_families() if f.name == family_name), None)
                if family_obj:
                    species_list = get_species_by_genus(genus_name, family_obj.id)
                    species_names = [s.name for s in species_list]
                else:
                    species_names = []
            else:
                species_names = []
        else:
            species_names = []
        
        species_option = st.selectbox(
            "Вид", 
            ["Добавить новый вид..."] + species_names
        )
        if species_option == "Добавить новый вид...":
            new_species = st.text_input("Название нового вида (эпитет)")
            species_name = None
        else:
            new_species = None
            species_name = species_option
        
        collector = st.text_input("Коллектор")
        collection_date = st.text_input("Дата сбора (ГГГГ-ММ-ДД)")
        location = st.text_input("Место сбора")
        
        st.subheader("Гербарный снимок")
        uploaded_file = st.file_uploader("Загрузите изображение", type=['jpg', 'jpeg', 'png', 'gif'])
        if uploaded_file is not None:
            st.image(uploaded_file, caption="Предпросмотр", width=300)
        
        st.subheader("Морфологические признаки")
        traits = get_traits()
        trait_options = {t.name: t for t in traits}
        
        add_new_trait = st.checkbox("Добавить новый признак")
        if add_new_trait:
            new_trait_name = st.text_input("Название нового признака")
            new_trait_unit = st.text_input("Единица измерения (опционально)")
            new_trait_type = st.selectbox("Тип данных", ["float", "integer", "category"])
            if st.button("Добавить признак", key="add_trait_in_form"):
                if new_trait_name:
                    success, msg = add_trait(new_trait_name, new_trait_unit, new_trait_type)
                    if success:
                        st.success(f"✅ {msg}")
                        st.rerun()
                    else:
                        st.error(f"❌ {msg}")
                else:
                    st.warning("Введите название признака")
        
        available_traits = get_traits()
        trait_options = {t.name: t for t in available_traits}
        selected_trait_names = st.multiselect("Выберите признаки для заполнения", list(trait_options.keys()))
        trait_values = {}
        for tname in selected_trait_names:
            trait_obj = trait_options[tname]
            if trait_obj.data_type in ('float', 'integer'):
                val = st.number_input(f"{tname} ({trait_obj.unit})", value=0.0, step=0.1)
            else:
                val = st.text_input(f"{tname} (значение)")
            trait_values[trait_obj.id] = str(val)
        
        submitted = st.form_submit_button("Сохранить образец")
        if submitted:
            if not family_name:
                st.error("Введите или выберите семейство")
                st.stop()
            if not genus_name:
                st.error("Введите или выберите род")
                st.stop()
            if species_option == "Добавить новый вид..." and not new_species:
                st.error("Введите название нового вида")
                st.stop()
            if species_option not in ["Добавить новый вид...", ""] and not species_name:
                st.error("Выберите вид")
                st.stop()
            
            success, msg = add_specimen(
                family_name, 
                genus_name, 
                species_name, 
                new_species if species_option == "Добавить новый вид..." else None,
                collector, 
                collection_date, 
                location, 
                trait_values, 
                uploaded_file
            )
            if success:
                st.success(f"✅ {msg}")
            else:
                st.error(f"❌ Ошибка: {msg}")

# ---------- Вкладка 2: Добавление таксонов и признаков ----------
with tab2:
    st.header("Добавление новых таксонов и признаков")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.subheader("Семейство")
        new_family = st.text_input("Название семейства", key="new_family")
        if st.button("Добавить семейство", key="add_family_btn"):
            if new_family:
                success, msg = add_family(new_family)
                if success:
                    st.success(f"✅ {msg}")
                    st.rerun()
                else:
                    st.error(f"❌ {msg}")
            else:
                st.warning("Введите название")
    
    with col2:
        st.subheader("Род")
        family_for_genus = st.selectbox("Семейство", [f.name for f in get_families()], key="family_for_genus")
        new_genus = st.text_input("Название рода", key="new_genus")
        if st.button("Добавить род", key="add_genus_btn"):
            if new_genus:
                success, msg = add_genus(new_genus, family_for_genus)
                if success:
                    st.success(f"✅ {msg}")
                    st.rerun()
                else:
                    st.error(f"❌ {msg}")
            else:
                st.warning("Введите название")
    
    with col3:
        st.subheader("Признак")
        new_trait_name = st.text_input("Название признака", key="new_trait_name")
        new_trait_unit = st.text_input("Единица измерения", key="new_trait_unit")
        new_trait_type = st.selectbox("Тип данных", ["float", "integer", "category"], key="new_trait_type")
        if st.button("Добавить признак", key="add_trait_btn2"):
            if new_trait_name:
                success, msg = add_trait(new_trait_name, new_trait_unit, new_trait_type)
                if success:
                    st.success(f"✅ {msg}")
                    st.rerun()
                else:
                    st.error(f"❌ {msg}")
            else:
                st.warning("Введите название")

# ---------- Вкладка 3: Просмотр ----------
with tab3:
    st.header("Просмотр образцов")
    specimens = get_filtered_specimens(
        family_name=selected_family,
        genus_name=selected_genus,
        location=location_filter,
        collector=collector_filter,
        date_from=date_from if date_from else None,
        date_to=date_to if date_to else None,
        has_image=has_image_flag,
        search_text=search_text if search_text else None,
        limit=limit
    )
    
    if not specimens:
        st.info("Нет образцов, соответствующих фильтрам.")
    else:
        data = []
        for s in specimens:
            measurements = {m.trait.name: m.value for m in s.measurements}
            row = {
                "ID": s.id,
                "Вид": s.species.name,
                "Род": s.species.genus.name,
                "Семейство": s.species.genus.family.name,
                "Коллектор": s.collector,
                "Дата": s.collection_date,
                "Место": s.location,
                **measurements
            }
            if s.image_path:
                row["Изображение"] = "Есть"
            data.append(row)
        df = pd.DataFrame(data)
        st.dataframe(df, use_container_width=True)
        
        # Подсчёт общего количества записей по фильтру (без лимита)
        total_count = len(get_filtered_specimens(
            family_name=selected_family,
            genus_name=selected_genus,
            location=location_filter,
            collector=collector_filter,
            date_from=date_from if date_from else None,
            date_to=date_to if date_to else None,
            has_image=has_image_flag,
            search_text=search_text if search_text else None,
            limit=None
        ))
        st.caption(f"Показано {len(df)} записей из {total_count} (всего по фильтру)")
        
        # Просмотр изображений для выбранного образца
        if specimens:
            st.subheader("Просмотр изображений")
            specimen_ids = [s.id for s in specimens]
            selected_id = st.selectbox("Выберите ID образца для просмотра изображения", specimen_ids)
            if selected_id:
                selected_specimen = next((s for s in specimens if s.id == selected_id), None)
                if selected_specimen and selected_specimen.image_path:
                    try:
                        img = Image.open(selected_specimen.image_path)
                        st.image(img, caption=f"Образец #{selected_id}", width=800, use_container_width=False)
                        with open(selected_specimen.image_path, "rb") as f:
                            st.download_button(
                                label="Скачать оригинал изображения",
                                data=f,
                                file_name=os.path.basename(selected_specimen.image_path),
                                mime="image/jpeg"
                            )
                    except Exception as e:
                        st.error(f"Не удалось загрузить изображение: {e}")
                else:
                    st.info("Изображение отсутствует")

# ---------- Вкладка 4: Графики ----------
with tab4:
    st.header("Построение графиков")
    specimens_all = get_filtered_specimens(
        family_name=selected_family,
        genus_name=selected_genus,
        location=location_filter,
        collector=collector_filter,
        date_from=date_from if date_from else None,
        date_to=date_to if date_to else None,
        has_image=has_image_flag,
        search_text=search_text if search_text else None,
        limit=None
    )
    
    if not specimens_all:
        st.info("Нет данных для построения графиков.")
    else:
        data_graph = []
        for s in specimens_all:
            row = {
                "ID": s.id,
                "Вид": s.species.name,
                "Род": s.species.genus.name,
                "Семейство": s.species.genus.family.name,
            }
            for m in s.measurements:
                try:
                    val = float(m.value)
                    row[m.trait.name] = val
                except (ValueError, TypeError):
                    pass
            data_graph.append(row)
        df_graph = pd.DataFrame(data_graph)
        
        if df_graph.empty or df_graph.select_dtypes(include=['float', 'int']).empty:
            st.warning("Нет числовых признаков для построения графиков.")
        else:
            numeric_cols = df_graph.select_dtypes(include=['float', 'int']).columns.tolist()
            numeric_cols = [c for c in numeric_cols if c != 'ID']
            if not numeric_cols:
                st.warning("Нет числовых признаков.")
            else:
                x_axis = st.selectbox("Ось X (признак)", numeric_cols)
                y_axis = st.selectbox("Ось Y (признак)", [c for c in numeric_cols if c != x_axis])
                color_by = st.selectbox("Цвет (группировка)", ["Семейство", "Род", "Вид"])
                chart_type = st.radio("Тип графика", ["Scatter", "Boxplot", "Violin", "Histogram"], horizontal=True)
                
                if chart_type == "Scatter":
                    fig = px.scatter(df_graph, x=x_axis, y=y_axis, color=color_by,
                                     hover_data=["ID", "Вид", "Род", "Семейство"],
                                     title=f"{y_axis} vs {x_axis}")
                elif chart_type == "Boxplot":
                    fig = px.box(df_graph, x=color_by, y=y_axis, color=color_by,
                                 title=f"Распределение {y_axis} по {color_by}")
                elif chart_type == "Violin":
                    fig = px.violin(df_graph, x=color_by, y=y_axis, color=color_by,
                                    box=True, title=f"Распределение {y_axis} по {color_by}")
                elif chart_type == "Histogram":
                    fig = px.histogram(df_graph, x=x_axis, color=color_by,
                                       title=f"Гистограмма {x_axis} по {color_by}")
                
                st.plotly_chart(fig, use_container_width=True)

# ---------- Вкладка 5: Импорт из Excel ----------
with tab5:
    st.header("Импорт образцов из Excel")
    st.markdown("""
    **Инструкция:** 
    - Загрузите файл `.xlsx` с колонками: **Семейство**, **Род**, **Вид**, **Коллектор**, **Дата_сбора**, **Место_сбора**.
    - Дополнительные колонки интерпретируются как **морфологические признаки** (название колонки должно совпадать с названием признака в системе; если признака нет, он будет создан автоматически с типом `float`).
    - Если вид не найден, он будет создан автоматически.
    - Строки с пропущенными обязательными полями будут пропущены с ошибкой.
    """)
    
    uploaded_excel = st.file_uploader("Выберите Excel-файл", type=["xlsx"])
    
    if uploaded_excel is not None:
        try:
            df = pd.read_excel(uploaded_excel)
            st.write("**Предпросмотр данных (первые 10 строк):**")
            st.dataframe(df.head(10))
            
            if st.button("Импортировать данные"):
                with st.spinner("Импорт..."):
                    added, errors = import_from_excel(df)
                    if added > 0:
                        st.success(f"Успешно импортировано {added} образцов!")
                    else:
                        st.warning("Не удалось импортировать ни одной записи.")
                    if errors:
                        st.warning("Обнаружены ошибки при импорте:")
                        for err in errors[:10]:
                            st.write(f"- {err}")
                        if len(errors) > 10:
                            st.write(f"... и ещё {len(errors)-10} ошибок.")
        except Exception as e:
            st.error(f"Ошибка чтения файла: {e}")