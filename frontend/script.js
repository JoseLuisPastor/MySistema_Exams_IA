// 🌐 CONFIGURACIÓN DE PRODUCCIÓN
// ⚠️ IMPORTANTE: Cambia esta URL por tu dominio real de Render
const API_BASE_URL = 'https://mi-sistema-examenes-backend.onrender.com';

// Variables globales
let currentTeacherId = null;
let currentExamId = null;
let currentStudentExam = null;
let currentQuestionIndex = 0;
let studentAnswers = {};
let examTimer = null;
let timeRemaining = 0;

// 🔍 Función para verificar el estado del backend
async function checkBackendHealth() {
    try {
        console.log('Verificando estado del backend...');
        const response = await fetch(`${API_BASE_URL}/health`);
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        const health = await response.json();
        console.log('✅ Backend status:', health);
        return health.status === 'OK';
    } catch (error) {
        console.error('❌ Backend no disponible:', error);
        showBackendError();
        return false;
    }
}

// 🚨 Mostrar error de backend
function showBackendError() {
    const errorDiv = document.createElement('div');
    errorDiv.innerHTML = `
        <div style="position: fixed; top: 10px; right: 10px; background: #f44336; color: white; padding: 10px; border-radius: 5px; z-index: 9999;">
            ⚠️ Backend no disponible. Puede tomar unos minutos en iniciarse la primera vez.
            <button onclick="this.parentElement.remove()" style="margin-left: 10px; background: none; border: none; color: white;">✕</button>
        </div>
    `;
    document.body.appendChild(errorDiv);
    
    // Auto-remove after 10 seconds
    setTimeout(() => {
        if (errorDiv.parentElement) {
            errorDiv.remove();
        }
    }, 10000);
}

// 📡 Función mejorada para fetch con manejo de errores
async function apiCall(url, options = {}) {
    const fullUrl = url.startsWith('http') ? url : `${API_BASE_URL}${url}`;
    
    try {
        console.log('🌐 API Call:', fullUrl, options);
        
        const response = await fetch(fullUrl, {
            ...options,
            headers: {
                ...options.headers,
                // Agregar headers para CORS si es necesario
            }
        });
        
        if (!response.ok) {
            const errorText = await response.text();
            throw new Error(`HTTP ${response.status}: ${errorText}`);
        }
        
        const data = await response.json();
        console.log('✅ API Response:', data);
        return data;
        
    } catch (error) {
        console.error('❌ API Error:', error);
        
        // Mostrar error específico al usuario
        if (error.message.includes('Failed to fetch')) {
            showBackendError();
            throw new Error('No se pudo conectar al servidor. Intenta de nuevo en unos minutos.');
        }
        
        throw error;
    }
}

// Funciones de navegación
function showHome() {
    hideAllPages();
    document.getElementById('home-page').classList.add('active');
}

function showTeacherLogin() {
    hideAllPages();
    document.getElementById('teacher-login').classList.add('active');
}

function showStudentLogin() {
    hideAllPages();
    document.getElementById('student-login').classList.add('active');
}

function showTeacherDashboard() {
    hideAllPages();
    document.getElementById('teacher-dashboard').classList.add('active');
    loadTeacherData();
}

function hideAllPages() {
    document.querySelectorAll('.page').forEach(page => {
        page.classList.remove('active');
    });
}

function showTab(tabId) {
    document.querySelectorAll('.tab-content').forEach(tab => {
        tab.classList.remove('active');
    });
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    
    document.getElementById(tabId).classList.add('active');
    event.target.classList.add('active');
    
    if (tabId === 'exams-section') {
        loadExams();
    } else if (tabId === 'grades-section') {
        loadGrades();
    }
}

function showLoading() {
    document.getElementById('loading').style.display = 'flex';
}

function hideLoading() {
    document.getElementById('loading').style.display = 'none';
}

// Inicialización
document.addEventListener('DOMContentLoaded', async function() {
    console.log('🚀 Iniciando aplicación...');
    
    // Verificar estado del backend al cargar
    await checkBackendHealth();
    
    // Configurar drag & drop para PDF
    const uploadArea = document.getElementById('upload-area');
    const fileInput = document.getElementById('pdf-file');
    
    uploadArea.addEventListener('click', () => fileInput.click());
    uploadArea.addEventListener('dragover', handleDragOver);
    uploadArea.addEventListener('drop', handleDrop);
    uploadArea.addEventListener('dragleave', handleDragLeave);
    
    fileInput.addEventListener('change', handleFileSelect);
    
    // Configurar formularios
    document.getElementById('teacher-form').addEventListener('submit', handleTeacherRegister);
    document.getElementById('student-form').addEventListener('submit', handleStudentLogin);
    
    // Configurar tiempo personalizado
    document.getElementById('time-limit').addEventListener('change', function() {
        const customTime = document.getElementById('custom-time');
        if (this.value === 'custom') {
            customTime.style.display = 'block';
        } else {
            customTime.style.display = 'none';
        }
    });
    
    console.log('✅ Aplicación inicializada correctamente');
});

// Manejo de archivos PDF
function handleDragOver(e) {
    e.preventDefault();
    e.currentTarget.classList.add('dragover');
}

function handleDragLeave(e) {
    e.currentTarget.classList.remove('dragover');
}

function handleDrop(e) {
    e.preventDefault();
    e.currentTarget.classList.remove('dragover');
    const files = e.dataTransfer.files;
    if (files.length > 0) {
        handleFile(files[0]);
    }
}

function handleFileSelect(e) {
    if (e.target.files.length > 0) {
        handleFile(e.target.files[0]);
    }
}

async function handleFile(file) {
    if (file.type !== 'application/pdf') {
        alert('Por favor selecciona un archivo PDF');
        return;
    }
    
    showLoading();
    const formData = new FormData();
    formData.append('file', file);
    formData.append('teacher_id', currentTeacherId);
    
    try {
        const data = await apiCall('/upload-pdf', {
            method: 'POST',
            body: formData
        });
        
        if (data.success) {
            document.getElementById('upload-area').innerHTML = `
                <p>✅ Archivo subido: ${data.filename}</p>
                <p>📑 Preguntas extraídas: ${data.num_preguntas}</p>
            `;
            document.getElementById('exam-config').style.display = 'block';
            window.currentFilePath = data.file_path;
        } else {
            throw new Error(data.error || 'Error al subir archivo');
        }
    } catch (error) {
        alert('Error al subir archivo: ' + error.message);
    } finally {
        hideLoading();
    }
}

// Registro de maestro
async function handleTeacherRegister(e) {
    e.preventDefault();
    const name = document.getElementById('teacher-name').value;
    const email = document.getElementById('teacher-email').value;
    
    if (!name.trim() || !email.trim()) {
        alert('Por favor completa todos los campos');
        return;
    }
    
    showLoading();
    
    try {
        const data = await apiCall('/register-teacher', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name: name.trim(), email: email.trim() })
        });
        
        if (data.success) {
            currentTeacherId = data.teacher_id;
            console.log('✅ Maestro registrado:', currentTeacherId);
            showTeacherDashboard();
        } else {
            throw new Error(data.error || 'Error en el registro');
        }
    } catch (error) {
        if (error.message.includes('Email already exists')) {
            alert('Este email ya está registrado. Si eres el maestro, tu ID debería estar guardado localmente.');
        } else {
            alert('Error en el registro: ' + error.message);
        }
    } finally {
        hideLoading();
    }
}

// Generar examen
async function generateExam() {
    const numQuestions = document.getElementById('num-questions').value;
    const timeLimit = document.getElementById('time-limit').value;
    const difficulty = document.getElementById('difficulty').value;
    
    let finalTimeLimit = timeLimit;
    if (timeLimit === 'custom') {
        finalTimeLimit = document.getElementById('custom-time-input').value;
        if (!finalTimeLimit || finalTimeLimit <= 0) {
            alert('Por favor ingresa un tiempo válido en minutos');
            return;
        }
    }
    
    if (!window.currentFilePath) {
        alert('Por favor sube un archivo PDF primero');
        return;
    }
    
    showLoading();
    
    try {
        const data = await apiCall('/generate-exam', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                teacher_id: currentTeacherId,
                file_path: window.currentFilePath,
                num_questions: parseInt(numQuestions),
                difficulty: difficulty,
                time_limit: parseInt(finalTimeLimit)
            })
        });
        
        if (data.success) {
            alert(`¡Examen generado exitosamente!\nCódigo: ${data.exam_code}`);
            document.getElementById('exam-config').style.display = 'none';
            document.getElementById('upload-area').innerHTML = '<p>Arrastra un archivo PDF aquí o haz clic para seleccionar</p>';
            loadExams();
            showTab('exams-section');
        } else {
            throw new Error(data.error || 'Error al generar examen');
        }
    } catch (error) {
        alert('Error al generar examen: ' + error.message);
    } finally {
        hideLoading();
    }
}

// Cargar datos del maestro
function loadTeacherData() {
    if (currentTeacherId) {
        loadExams();
    }
}

async function loadExams() {
    if (!currentTeacherId) {
        console.warn('No hay teacher ID disponible');
        return;
    }
    
    try {
        const data = await apiCall(`/get-teacher-exams/${currentTeacherId}`);
        
        const examsList = document.getElementById('exams-list');
        if (!data.exams || data.exams.length === 0) {
            examsList.innerHTML = '<p>No hay exámenes generados aún.</p>';
            return;
        }
        
        examsList.innerHTML = data.exams.map(exam => `
            <div class="exam-list-item">
                <div class="exam-info">
                    <h4>Código: ${exam.exam_code}</h4>
                    <p>Preguntas: ${exam.num_questions} | Dificultad: ${exam.difficulty}</p>
                    <p>Versiones: ${exam.versions} | Creado: ${new Date(exam.created_at).toLocaleDateString()}</p>
                </div>
                <div class="exam-actions">
                    <button class="btn btn-primary" onclick="showVersionsPage('${exam.exam_id}')">
                        Generar Versiones
                    </button>
                </div>
            </div>
        `).join('');
    } catch (error) {
        console.error('Error cargando exámenes:', error);
        document.getElementById('exams-list').innerHTML = 
            '<p>Error al cargar exámenes. Revisa tu conexión e intenta de nuevo.</p>';
    }
}

async function loadGrades() {
    if (!currentTeacherId) {
        console.log('No teacher ID available');
        return;
    }
    
    console.log('Loading grades for teacher:', currentTeacherId);
    
    try {
        const data = await apiCall(`/get-student-results/${currentTeacherId}`);
        
        console.log('Student results data:', data);
        
        const gradesList = document.getElementById('grades-list');
        if (!data.results || data.results.length === 0) {
            gradesList.innerHTML = '<p>No hay calificaciones aún. Los estudiantes deben completar exámenes para que aparezcan los resultados aquí.</p>';
            return;
        }
        
        gradesList.innerHTML = data.results.map(result => `
            <div class="grade-item">
                <div class="grade-info">
                    <h4>${result.student_name}</h4>
                    <p>Examen: ${result.exam_code} | Calificación: ${result.overall_percentage}%</p>
                    <p>Fecha: ${new Date(result.submitted_at).toLocaleDateString()}</p>
                    <p><strong>Estado:</strong> ${result.overall_percentage >= 60 ? 'Aprobado' : 'Reprobado'}</p>
                </div>
                <div class="grade-actions">
                    <button class="btn btn-primary" onclick="showStudentDetails('${result.result_id}')">
                        Ver Detalles
                    </button>
                </div>
            </div>
        `).join('');
    } catch (error) {
        console.error('Error cargando calificaciones:', error);
        const gradesList = document.getElementById('grades-list');
        gradesList.innerHTML = '<p>Error al cargar las calificaciones. Revisa la consola para más detalles.</p>';
    }
}

// Versiones de exámenes
function showVersionsPage(examId) {
    currentExamId = examId;
    hideAllPages();
    document.getElementById('versions-page').classList.add('active');
}

async function generateVersions() {
    const numVersions = document.getElementById('num-versions').value;
    
    if (!numVersions || numVersions <= 0) {
        alert('Por favor ingresa un número válido de versiones');
        return;
    }
    
    showLoading();
    
    try {
        const data = await apiCall('/generate-exam-versions', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                exam_id: currentExamId,
                num_versions: parseInt(numVersions)
            })
        });
        
        if (data.success) {
            const resultDiv = document.getElementById('versions-result');
            resultDiv.innerHTML = `
                <div class="alert alert-success">
                    ✅ ${data.versions.length} versiones generadas exitosamente:
                </div>
                ${data.versions.map(version => `
                    <div class="version-item">
                        <strong>Código:</strong> ${version.version_code}
                    </div>
                `).join('')}
            `;
        } else {
            throw new Error(data.error || 'Error al generar versiones');
        }
    } catch (error) {
        alert('Error al generar versiones: ' + error.message);
    } finally {
        hideLoading();
    }
}

// Login de estudiante
async function handleStudentLogin(e) {
    e.preventDefault();
    const studentName = document.getElementById('student-name').value;
    const examCode = document.getElementById('exam-code').value;
    
    if (!studentName.trim() || !examCode.trim()) {
        alert('Por favor completa todos los campos');
        return;
    }
    
    showLoading();
    
    try {
        const data = await apiCall(`/get-exam/${examCode.trim()}`);
        
        if (data.error) {
            alert('Código de examen no válido');
            return;
        }
        
        currentStudentExam = data;
        window.currentStudentName = studentName.trim();
        window.currentExamCode = examCode.trim();
        startExam();
    } catch (error) {
        alert('Error al obtener examen: ' + error.message);
    } finally {
        hideLoading();
    }
}

// Funciones del examen
function startExam() {
    hideAllPages();
    document.getElementById('student-exam').classList.add('active');
    
    currentQuestionIndex = 0;
    studentAnswers = {};
    timeRemaining = currentStudentExam.time_limit * 60; // minutos a segundos
    
    displayQuestion();
    startTimer();
}

function displayQuestion() {
    const question = currentStudentExam.questions[currentQuestionIndex];
    const totalQuestions = currentStudentExam.questions.length;
    
    document.getElementById('current-question').textContent = 
        `Pregunta ${currentQuestionIndex + 1} de ${totalQuestions}`;
    document.getElementById('question-text').textContent = question.pregunta;
    
    const optionsContainer = document.getElementById('options-container');
    optionsContainer.innerHTML = Object.entries(question.opciones).map(([key, value]) => `
        <div class="option" onclick="selectOption('${key}')" data-option="${key}">
            <strong>${key})</strong> ${value}
        </div>
    `).join('');
    
    // Mostrar respuesta previa si existe
    if (studentAnswers[currentQuestionIndex]) {
        const selectedOption = document.querySelector(`[data-option="${studentAnswers[currentQuestionIndex]}"]`);
        if (selectedOption) {
            selectedOption.classList.add('selected');
        }
    }
    
    // Controlar botones de navegación
    document.getElementById('prev-btn').disabled = currentQuestionIndex === 0;
    
    if (currentQuestionIndex === totalQuestions - 1) {
        document.getElementById('next-btn').style.display = 'none';
        document.getElementById('finish-btn').style.display = 'inline-block';
    } else {
        document.getElementById('next-btn').style.display = 'inline-block';
        document.getElementById('finish-btn').style.display = 'none';
    }
}

function selectOption(option) {
    // Remover selección previa
    document.querySelectorAll('.option').forEach(opt => {
        opt.classList.remove('selected');
    });
    
    // Seleccionar nueva opción
    const selectedElement = document.querySelector(`[data-option="${option}"]`);
    selectedElement.classList.add('selected');
    
    // Guardar respuesta
    studentAnswers[currentQuestionIndex] = option;
}

function nextQuestion() {
    if (!studentAnswers[currentQuestionIndex]) {
        alert('Por favor selecciona una respuesta antes de continuar');
        return;
    }
    
    if (currentQuestionIndex < currentStudentExam.questions.length - 1) {
        currentQuestionIndex++;
        displayQuestion();
    }
}

function previousQuestion() {
    if (currentQuestionIndex > 0) {
        currentQuestionIndex--;
        displayQuestion();
    }
}

function startTimer() {
    examTimer = setInterval(() => {
        timeRemaining--;
        
        const minutes = Math.floor(timeRemaining / 60);
        const seconds = timeRemaining % 60;
        document.getElementById('timer').textContent = 
            `${minutes}:${seconds.toString().padStart(2, '0')}`;
        
        // Cambiar color cuando queden menos de 5 minutos
        if (timeRemaining <= 300) { // 5 minutos
            document.getElementById('timer').style.color = '#ff4444';
        }
        
        if (timeRemaining <= 0) {
            clearInterval(examTimer);
            alert('¡Tiempo agotado! El examen se enviará automáticamente.');
            finishExam();
        }
    }, 1000);
}

async function finishExam() {
    clearInterval(examTimer);
    
    // Verificar que haya al menos una respuesta
    if (Object.keys(studentAnswers).length === 0) {
        if (!confirm('No has respondido ninguna pregunta. ¿Estás seguro de que quieres enviar el examen?')) {
            return;
        }
    }
    
    showLoading();
    
    try {
        const data = await apiCall('/submit-exam', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                student_name: window.currentStudentName,
                exam_code: window.currentExamCode,
                answers: studentAnswers
            })
        });
        
        if (data.success) {
            showResults(data);
        } else {
            throw new Error(data.error || 'Error al enviar examen');
        }
    } catch (error) {
        alert('Error al enviar examen: ' + error.message);
    } finally {
        hideLoading();
    }
}

function showResults(data) {
    hideAllPages();
    document.getElementById('student-results').classList.add('active');
    
    document.getElementById('overall-score').textContent = `${data.overall_percentage}%`;
    document.getElementById('correct-count').textContent = data.correct_answers;
    document.getElementById('total-count').textContent = data.total_questions;
    document.getElementById('grade-status').textContent = 
        data.overall_percentage >= 60 ? 'Aprobado' : 'Reprobado';
    
    // Actualizar color del círculo según calificación
    const scoreCircle = document.querySelector('.score-circle');
    if (data.overall_percentage >= 60) {
        scoreCircle.style.background = 'linear-gradient(135deg, #4CAF50, #45a049)';
    } else {
        scoreCircle.style.background = 'linear-gradient(135deg, #f44336, #d32f2f)';
    }
    
    const topicsList = document.getElementById('topics-list');
    topicsList.innerHTML = Object.entries(data.topic_scores).map(([topic, scores]) => `
        <div class="topic-item">
            <div class="topic-name">${topic}</div>
            <div class="topic-score">
                <div class="topic-percentage">${scores.percentage}%</div>
                <div class="topic-status ${scores.status.toLowerCase()}">${scores.status}</div>
                <div>${scores.correct}/${scores.total}</div>
            </div>
        </div>
    `).join('');
}

async function showStudentDetails(resultId) {
    showLoading();
    
    try {
        const data = await apiCall(`/get-student-details/${resultId}`);
        
        if (data.error) {
            throw new Error(data.error);
        }
        
        hideAllPages();
        document.getElementById('student-details').classList.add('active');
        
        const detailContent = document.getElementById('student-detail-content');
        detailContent.innerHTML = `
            <div class="student-detail-header">
                <h3>Detalles de ${data.student_name}</h3>
                <p><strong>Código de Examen:</strong> ${data.exam_code}</p>
                <p><strong>Fecha:</strong> ${new Date(data.submitted_at).toLocaleString()}</p>
            </div>
            
            <div class="results-summary">
                <div class="score-circle ${data.overall_percentage >= 60 ? 'approved' : 'failed'}">
                    <span>${data.overall_percentage}%</span>
                </div>
                <div class="score-details">
                    <p><strong>Preguntas correctas:</strong> ${data.correct_answers} de ${data.total_questions}</p>
                    <p><strong>Estado general:</strong> ${data.overall_percentage >= 60 ? 'Aprobado' : 'Reprobado'}</p>
                </div>
            </div>
            
            <div class="topics-breakdown">
                <h4>Desglose por Temas</h4>
                <div class="topics-list">
                    ${Object.entries(data.topic_scores).map(([topic, scores]) => `
                        <div class="topic-item">
                            <div class="topic-name">${topic}</div>
                            <div class="topic-score">
                                <div class="topic-percentage">${scores.percentage}%</div>
                                <div class="topic-status ${scores.status.toLowerCase()}">${scores.status}</div>
                                <div class="topic-fraction">${scores.correct}/${scores.total}</div>
                            </div>
                        </div>
                    `).join('')}
                </div>
            </div>
        `;
    } catch (error) {
        alert('Error al cargar detalles: ' + error.message);
    } finally {
        hideLoading();
    }
}

// 🔧 Funciones de utilidad para debugging
window.debugApp = {
    checkBackend: checkBackendHealth,
    setTeacherId: (id) => { currentTeacherId = id; },
    getTeacherId: () => currentTeacherId,
    apiCall: apiCall
};

console.log('🎯 Script.js cargado. Usa window.debugApp para debugging.');