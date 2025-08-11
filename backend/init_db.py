#!/usr/bin/env python3
"""
Script para inicializar la base de datos PostgreSQL
Ejecuta este script una vez después de crear la base de datos en Render
"""

import os
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

def init_database():
    """Inicializar tablas de la base de datos"""
    DATABASE_URL = os.getenv('DATABASE_URL')
    
    if not DATABASE_URL:
        print("❌ Error: No se encontró DATABASE_URL en las variables de entorno")
        return False
    
    try:
        print("🔄 Conectando a la base de datos...")
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
        cur = conn.cursor()
        
        print("🔄 Creando tabla 'teachers'...")
        # Tabla de maestros
        cur.execute("""
            CREATE TABLE IF NOT EXISTS teachers (
                id VARCHAR(36) PRIMARY KEY,
                name VARCHAR(200) NOT NULL,
                email VARCHAR(200) UNIQUE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        print("🔄 Creando tabla 'exams'...")
        # Tabla de exámenes
        cur.execute("""
            CREATE TABLE IF NOT EXISTS exams (
                id VARCHAR(36) PRIMARY KEY,
                teacher_id VARCHAR(36) REFERENCES teachers(id),
                exam_code VARCHAR(10) UNIQUE NOT NULL,
                questions JSONB NOT NULL,
                time_limit INTEGER DEFAULT 40,
                difficulty VARCHAR(20) DEFAULT 'medium',
                versions INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        print("🔄 Creando tabla 'exam_versions'...")
        # Tabla de versiones de exámenes
        cur.execute("""
            CREATE TABLE IF NOT EXISTS exam_versions (
                id VARCHAR(36) PRIMARY KEY,
                original_exam_id VARCHAR(36) REFERENCES exams(id),
                version_code VARCHAR(10) UNIQUE NOT NULL,
                questions JSONB NOT NULL,
                time_limit INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        print("🔄 Creando tabla 'student_results'...")
        # Tabla de resultados de estudiantes
        cur.execute("""
            CREATE TABLE IF NOT EXISTS student_results (
                id VARCHAR(36) PRIMARY KEY,
                student_name VARCHAR(200) NOT NULL,
                exam_code VARCHAR(10) NOT NULL,
                exam_id VARCHAR(36),
                answers JSONB,
                correct_answers INTEGER,
                total_questions INTEGER,
                overall_percentage DECIMAL(5,2),
                topic_scores JSONB,
                submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        print("🔄 Creando índices para mejor rendimiento...")
        # Índices para mejorar rendimiento
        cur.execute("CREATE INDEX IF NOT EXISTS idx_teachers_email ON teachers(email)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_exams_teacher_id ON exams(teacher_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_exams_code ON exams(exam_code)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_versions_code ON exam_versions(version_code)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_results_exam_code ON student_results(exam_code)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_results_submitted_at ON student_results(submitted_at)")
        
        conn.commit()
        cur.close()
        conn.close()
        
        print("✅ Base de datos inicializada correctamente")
        print("📋 Tablas creadas:")
        print("   - teachers (maestros)")
        print("   - exams (exámenes)")
        print("   - exam_versions (versiones de exámenes)")
        print("   - student_results (resultados de estudiantes)")
        print("📈 Índices creados para optimizar consultas")
        
        return True
        
    except Exception as e:
        print(f"❌ Error inicializando base de datos: {e}")
        return False

def verify_connection():
    """Verificar que la conexión a la base de datos funciona"""
    DATABASE_URL = os.getenv('DATABASE_URL')
    
    if not DATABASE_URL:
        print("❌ Error: No se encontró DATABASE_URL")
        return False
    
    try:
        print("🔄 Verificando conexión a la base de datos...")
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        
        # Verificar versión de PostgreSQL
        cur.execute("SELECT version()")
        version = cur.fetchone()[0]
        print(f"✅ Conectado exitosamente a: {version}")
        
        # Verificar tablas creadas
        cur.execute("""
            SELECT table_name FROM information_schema.tables 
            WHERE table_schema = 'public' 
            ORDER BY table_name
        """)
        tables = cur.fetchall()
        
        if tables:
            print("📋 Tablas encontradas en la base de datos:")
            for table in tables:
                print(f"   - {table[0]}")
        else:
            print("⚠️ No se encontraron tablas en la base de datos")
        
        cur.close()
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Error verificando conexión: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Iniciando configuración de base de datos...")
    print("=" * 50)
    
    # Verificar conexión
    if not verify_connection():
        print("❌ No se pudo conectar a la base de datos. Verifica tus credenciales.")
        exit(1)
    
    # Inicializar tablas
    if init_database():
        print("\n🎉 ¡Base de datos configurada exitosamente!")
        print("🔥 Tu aplicación está lista para usar PostgreSQL")
    else:
        print("\n❌ Hubo un error configurando la base de datos")
        exit(1)
    
    print("=" * 50)
    print("📚 Próximos pasos:")
    print("1. Asegúrate de que las variables de entorno estén configuradas en Render")
    print("2. Despliega tu aplicación en Render")
    print("3. Prueba el endpoint /health para verificar que todo funciona")
    print("4. ¡Tu sistema de exámenes estará listo para usar!")
    print("\n💡 Tip: Guarda la DATABASE_URL en un lugar seguro para futuras referencias")