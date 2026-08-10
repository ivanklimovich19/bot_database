# models.py
from sqlalchemy import create_engine, Column, Integer, String, Float, ForeignKey, JSON
from sqlalchemy.orm import relationship, sessionmaker, declarative_base
from config import DATABASE_URL

Base = declarative_base()

class Family(Base):
    __tablename__ = 'families'
    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False)
    genera = relationship('Genus', back_populates='family')

class Genus(Base):
    __tablename__ = 'genera'
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    family_id = Column(Integer, ForeignKey('families.id'))
    family = relationship('Family', back_populates='genera')
    species = relationship('Species', back_populates='genus')

class Species(Base):
    __tablename__ = 'species'
    id = Column(Integer, primary_key=True)
    name = Column(String(150), nullable=False)
    genus_id = Column(Integer, ForeignKey('genera.id'))
    genus = relationship('Genus', back_populates='species')
    specimens = relationship('Specimen', back_populates='species')

class Specimen(Base):
    __tablename__ = 'specimens'
    id = Column(Integer, primary_key=True)
    species_id = Column(Integer, ForeignKey('species.id'))
    collector = Column(String(100))
    collection_date = Column(String(50))
    location = Column(String(200))
    image_path = Column(String(500))  # путь к изображению
    additional_data = Column(JSON)
    species = relationship('Species', back_populates='specimens')
    measurements = relationship('Measurement', back_populates='specimen')

class Trait(Base):
    __tablename__ = 'traits'
    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False)
    unit = Column(String(20))
    data_type = Column(String(20))  # 'float', 'integer', 'category'
    measurements = relationship('Measurement', back_populates='trait')

class Measurement(Base):
    __tablename__ = 'measurements'
    id = Column(Integer, primary_key=True)
    specimen_id = Column(Integer, ForeignKey('specimens.id'))
    trait_id = Column(Integer, ForeignKey('traits.id'))
    value = Column(String(200))
    specimen = relationship('Specimen', back_populates='measurements')
    trait = relationship('Trait', back_populates='measurements')

# Создаём движок и сессию
engine = create_engine(DATABASE_URL)
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine, expire_on_commit=False)