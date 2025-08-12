from flask import Flask, request, jsonify, render_template, session
from flask_cors import CORS
import os
import json
import uuid
from dotenv import load_dotenv
from datetime import datetime
from werkzeug.utils import secure_filename
import random
import psycopg2
import psycopg2.extras
from utils.pdf_processor import extract_text_from_pdf, extraer_preguntas, generate_exam

# Cargar variables de entorno
load_dotenv()

# Configuración de Flask
app = Flask(__name__, static_folder='../frontend', template_folder='../frontend')

# Configuración de CORS para producción
if os.getenv('FLASK_ENV') == 'production':
    # En producción, especifica tu dominio de Vercel
    CORS(app, origins=['https://my-sistema-exams-ia.vercel.app/'])
else:
    # En desarrollo, permite todos los orígenes
    CORS(app)

# Configuración de SECRET_KEY
secret_key = os.getenv("SECRET_KEY")
if not secret_key:
    # Generar una clave secreta temporal si no existe (solo para desarrollo)
    secret_key = str(uuid.uuid4())
    print("⚠️ Usando SECRET_KEY temporal. Configura una permanente en producción.")

app.secret_key = secret_key

# Configuración
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'pdf'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Crear directorio de uploads si no existe
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Configuración de base de datos
DATABASE_URL = os.getenv('DATABASE_URL')
if not DATABASE_URL:
    raise ValueError("⚠️ Falta la variable DATABASE_URL en las variables de entorno")

def get_db_connection():
    """Crear conexión a la base de datos PostgreSQL"""
    try:
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
        return conn
    except Exception as e:
        print(f"Error conectando a la base de datos: {e}")
        return None

def init_database():
    """Inicializar tablas de la base de datos"""
    conn = get_db_connection()
    if not conn:
        return False
    
    try:
        cur = conn.cursor()
        
        # Tabla de maestros
        cur.execute("""
            CREATE TABLE IF NOT EXISTS teachers (
                id VARCHAR(36) PRIMARY KEY,
                name VARCHAR(200) NOT NULL,
                email VARCHAR(200) UNIQUE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
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
        
        conn.commit()
        cur.close()
        conn.close()
        print("✅ Base de datos inicializada correctamente")
        return True
        
    except Exception as e:
        print(f"❌ Error inicializando base de datos: {e}")
        conn.rollback()
        cur.close()
        conn.close()
        return False

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/health', methods=['GET'])
def health_check():
    """Endpoint de salud para Render"""
    try:
        # Verificar conexión a la base de datos
        conn = get_db_connection()
        if conn:
            conn.close()
            return jsonify({
                "status": "OK", 
                "message": "Backend funcionando",
                "database": "connected",
                "timestamp": datetime.now().isoformat()
            })
        else:
            return jsonify({
                "status": "ERROR",
                "message": "Error de conexión a base de datos"
            }), 500
    except Exception as e:
        return jsonify({
            "status": "ERROR",
            "message": str(e)
        }), 500

@app.route('/')
def index():
    return render_template('index.html')

# Rutas para maestros
@app.route('/register-teacher', methods=['POST'])
def register_teacher():
    data = request.json
    teacher_id = str(uuid.uuid4())
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
    
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO teachers (id, name, email) VALUES (%s, %s, %s)",
            (teacher_id, data['name'], data['email'])
        )
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({'teacher_id': teacher_id, 'success': True})
        
    except psycopg2.IntegrityError:
        return jsonify({'error': 'Email already exists'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/login-teacher', methods=['POST'])
def login_teacher():
    data = request.json
    name = data['name']
    email = data['email']
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
    
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id FROM teachers WHERE name = %s AND email = %s",
            (name, email)
        )
        teacher = cur.fetchone()
        
        if teacher:
            cur.close()
            conn.close()
            return jsonify({
                'teacher_id': teacher['id'], 
                'success': True,
                'message': 'Login exitoso'
            })
        else:
            cur.close()
            conn.close()
            return jsonify({
                'success': False,
                'error': 'Credenciales incorrectas'
            }), 404
            
    except Exception as e:
        cur.close()
        conn.close()
        return jsonify({'error': str(e)}), 500

@app.route('/upload-pdf', methods=['POST'])
def upload_pdf():
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    
    file = request.files['file']
    teacher_id = request.form.get('teacher_id')
    
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        # Usar timestamp para evitar conflictos de nombres
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_filename = f"{timestamp}_{filename}"
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
        file.save(file_path)
        
        try:
            # Extraer texto y preguntas
            pdf_text = extract_text_from_pdf(file_path)
            preguntas = extraer_preguntas(pdf_text)
            
            return jsonify({
                'success': True,
                'filename': unique_filename,
                'num_preguntas': len(preguntas),
                'file_path': file_path
            })
        except Exception as e:
            # Limpiar archivo si hay error
            if os.path.exists(file_path):
                os.remove(file_path)
            return jsonify({'error': f'Error processing PDF: {str(e)}'}), 500
    
    return jsonify({'error': 'Invalid file type'}), 400

@app.route('/generate-exam', methods=['POST'])
def generate_exam_route():
    data = request.json

    # Validación básica
    if not data or 'teacher_id' not in data or 'file_path' not in data:
        return jsonify({"error": "Faltan parámetros obligatorios"}), 400

    teacher_id = data['teacher_id']
    file_path = data['file_path']
    num_questions = data.get('num_questions', 20)
    difficulty = data.get('difficulty', 'medium')
    time_limit = data.get('time_limit', 40)

    try:
        # Generar examen usando IA
        exam_data = generate_exam(file_path, num_questions, difficulty)

        print("exam_data recibido:", exam_data)

        # Verificar clave correcta (preguntas o questions)
        if not exam_data or ('preguntas' not in exam_data and 'questions' not in exam_data):
            return jsonify({"error": "La generación del examen falló, no hay preguntas."}), 400

        # Obtener preguntas usando la clave correcta
        preguntas = exam_data.get('preguntas') or exam_data.get('questions')

        exam_id = str(uuid.uuid4())
        exam_code = ''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789', k=6))

        # Guardar en base de datos
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500

        cur = conn.cursor()
        cur.execute("""
            INSERT INTO exams (id, teacher_id, exam_code, questions, time_limit, difficulty)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (exam_id, teacher_id, exam_code, json.dumps(preguntas), time_limit, difficulty))
        
        conn.commit()
        cur.close()
        conn.close()

        # Limpiar archivo PDF temporal
        if os.path.exists(file_path):
            os.remove(file_path)

        return jsonify({
            'exam_id': exam_id,
            'exam_code': exam_code,
            'questions': preguntas,
            'success': True
        })
        
    except Exception as e:
        return jsonify({"error": f"Error generando examen: {str(e)}"}), 500

@app.route('/get-teacher-exams/<teacher_id>')
def get_teacher_exams(teacher_id):
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
    
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT id, exam_code, questions, difficulty, versions, created_at
            FROM exams WHERE teacher_id = %s ORDER BY created_at DESC
        """, (teacher_id,))
        
        exams_data = cur.fetchall()
        cur.close()
        conn.close()
        
        teacher_exams = []
        for exam in exams_data:
            questions = json.loads(exam['questions']) if isinstance(exam['questions'], str) else exam['questions']
            teacher_exams.append({
                'exam_id': exam['id'],
                'exam_code': exam['exam_code'],
                'num_questions': len(questions),
                'difficulty': exam['difficulty'],
                'created_at': exam['created_at'].isoformat() if exam['created_at'] else None,
                'versions': exam['versions']
            })
        
        return jsonify({'exams': teacher_exams})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/generate-exam-versions', methods=['POST'])
def generate_exam_versions():
    data = request.json
    exam_id = data['exam_id']
    num_versions = data.get('num_versions', 1)
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
    
    try:
        # Obtener examen original
        cur = conn.cursor()
        cur.execute("SELECT * FROM exams WHERE id = %s", (exam_id,))
        original_exam = cur.fetchone()
        
        if not original_exam:
            return jsonify({'error': 'Exam not found'}), 404
        
        questions = json.loads(original_exam['questions']) if isinstance(original_exam['questions'], str) else original_exam['questions']
        versions = []
        
        for i in range(num_versions):
            version_id = str(uuid.uuid4())
            version_code = ''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789', k=6))
            
            # Mezclar preguntas
            shuffled_questions = questions.copy()
            random.shuffle(shuffled_questions)
            
            # Mezclar opciones de cada pregunta
            for question in shuffled_questions:
                if 'opciones' in question:
                    options = list(question['opciones'].items())
                    random.shuffle(options)
                    question['opciones'] = dict(options)
            
            # Guardar versión en base de datos
            cur.execute("""
                INSERT INTO exam_versions (id, original_exam_id, version_code, questions, time_limit)
                VALUES (%s, %s, %s, %s, %s)
            """, (version_id, exam_id, version_code, json.dumps(shuffled_questions), original_exam['time_limit']))
            
            versions.append({
                'version_id': version_id,
                'version_code': version_code
            })
        
        # Actualizar contador de versiones
        cur.execute(
            "UPDATE exams SET versions = versions + %s WHERE id = %s",
            (num_versions, exam_id)
        )
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({'versions': versions, 'success': True})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/get-exam/<exam_code>')
def get_exam(exam_code):
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
    
    try:
        cur = conn.cursor()
        
        # Buscar en exámenes originales
        cur.execute("SELECT * FROM exams WHERE exam_code = %s", (exam_code,))
        exam = cur.fetchone()
        
        if exam:
            questions = json.loads(exam['questions']) if isinstance(exam['questions'], str) else exam['questions']
            return jsonify({
                'exam_id': exam['id'],
                'questions': questions,
                'time_limit': exam['time_limit'],
                'is_version': False
            })
        
        # Buscar en versiones
        cur.execute("SELECT * FROM exam_versions WHERE version_code = %s", (exam_code,))
        version = cur.fetchone()
        
        if version:
            questions = json.loads(version['questions']) if isinstance(version['questions'], str) else version['questions']
            return jsonify({
                'exam_id': version['id'],
                'questions': questions,
                'time_limit': version['time_limit'],
                'is_version': True
            })
        
        cur.close()
        conn.close()
        return jsonify({'error': 'Exam not found'}), 404
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/submit-exam', methods=['POST'])
def submit_exam():
    data = request.json
    student_name = data['student_name']
    exam_code = data['exam_code']
    answers = data['answers']
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
    
    try:
        cur = conn.cursor()
        
        # Encontrar examen
        exam_data = None
        exam_id = None
        
        # Buscar en exámenes originales
        cur.execute("SELECT * FROM exams WHERE exam_code = %s", (exam_code,))
        exam = cur.fetchone()
        
        if exam:
            exam_data = exam
            exam_id = exam['id']
        else:
            # Buscar en versiones
            cur.execute("SELECT * FROM exam_versions WHERE version_code = %s", (exam_code,))
            version = cur.fetchone()
            if version:
                exam_data = version
                exam_id = version['id']
        
        if not exam_data:
            return jsonify({'error': 'Exam not found'}), 404
        
        questions = json.loads(exam_data['questions']) if isinstance(exam_data['questions'], str) else exam_data['questions']
        
        # Calcular calificación
        correct_answers = 0
        total_questions = len(questions)
        topic_scores = {}
        
        for i, question in enumerate(questions):
            topic = question.get('tema', 'General')
            if topic not in topic_scores:
                topic_scores[topic] = {'correct': 0, 'total': 0}
            
            topic_scores[topic]['total'] += 1
            
            if str(i) in answers and answers[str(i)] == question.get('respuesta_correcta'):
                correct_answers += 1
                topic_scores[topic]['correct'] += 1
        
        # Calcular porcentajes por tema
        topic_percentages = {}
        for topic, scores in topic_scores.items():
            percentage = (scores['correct'] / scores['total']) * 100
            topic_percentages[topic] = {
                'percentage': round(percentage, 2),
                'status': 'Aprobado' if percentage >= 60 else 'Reprobado',
                'correct': scores['correct'],
                'total': scores['total']
            }
        
        overall_percentage = (correct_answers / total_questions) * 100
        
        # Guardar resultado
        result_id = str(uuid.uuid4())
        cur.execute("""
            INSERT INTO student_results 
            (id, student_name, exam_code, exam_id, answers, correct_answers, 
             total_questions, overall_percentage, topic_scores)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (result_id, student_name, exam_code, exam_id, json.dumps(answers),
              correct_answers, total_questions, round(overall_percentage, 2), 
              json.dumps(topic_percentages)))
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({
            'result_id': result_id,
            'correct_answers': correct_answers,
            'total_questions': total_questions,
            'overall_percentage': round(overall_percentage, 2),
            'topic_scores': topic_percentages,
            'success': True
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/get-student-results/<teacher_id>')
def get_student_results(teacher_id):
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
    
    try:
        cur = conn.cursor()
        
        # Obtener resultados de exámenes del maestro
        cur.execute("""
            SELECT sr.* FROM student_results sr
            JOIN exams e ON sr.exam_code = e.exam_code
            WHERE e.teacher_id = %s
            UNION
            SELECT sr.* FROM student_results sr
            JOIN exam_versions ev ON sr.exam_code = ev.version_code
            JOIN exams e ON ev.original_exam_id = e.id
            WHERE e.teacher_id = %s
            ORDER BY submitted_at DESC
        """, (teacher_id, teacher_id))
        
        results_data = cur.fetchall()
        cur.close()
        conn.close()
        
        results = []
        for result in results_data:
            topic_scores = json.loads(result['topic_scores']) if isinstance(result['topic_scores'], str) else result['topic_scores']
            results.append({
                'result_id': result['id'],
                'student_name': result['student_name'],
                'exam_code': result['exam_code'],
                'overall_percentage': float(result['overall_percentage']),
                'submitted_at': result['submitted_at'].isoformat() if result['submitted_at'] else None,
                'topic_scores': topic_scores
            })
        
        return jsonify({'results': results})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/get-student-details/<result_id>')
def get_student_details(result_id):
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500
    
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM student_results WHERE id = %s", (result_id,))
        result = cur.fetchone()
        cur.close()
        conn.close()
        
        if not result:
            return jsonify({'error': 'Result not found'}), 404
        
        # Convertir a diccionario serializable
        result_data = dict(result)
        
        # Parsear JSON fields
        if isinstance(result_data['answers'], str):
            result_data['answers'] = json.loads(result_data['answers'])
        if isinstance(result_data['topic_scores'], str):
            result_data['topic_scores'] = json.loads(result_data['topic_scores'])
        
        # Convertir timestamp a string
        if result_data['submitted_at']:
            result_data['submitted_at'] = result_data['submitted_at'].isoformat()
        
        # Convertir Decimal a float
        if result_data['overall_percentage']:
            result_data['overall_percentage'] = float(result_data['overall_percentage'])
        
        return jsonify(result_data)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    # Inicializar base de datos al arrancar
    init_database()
    
    # Configuración para producción vs desarrollo
    if os.getenv('FLASK_ENV') == 'production':
        # Configuración para Render
        port = int(os.environ.get('PORT', 5000))
        app.run(host='0.0.0.0', port=port, debug=False)
    else:
        # Configuración para desarrollo local
        app.run(debug=True, port=5000)
