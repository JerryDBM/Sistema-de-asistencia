"""Ventana de escritorio que ayuda al docente a administrar clases y asistencia."""

# `os` lee ajustes del sistema, `sys` gestiona el inicio y cierre, y `csv` crea archivos de hoja de cálculo.
# `threading` ayuda a detener el lector de cámara; `datetime` obtiene la fecha y hora actuales.
# `requests` permite comunicarse con el servidor y `load_dotenv` carga opciones desde un archivo `.env`.
import os
import sys
import csv
import threading
from datetime import datetime
import requests
from dotenv import load_dotenv

# Elementos básicos de Qt: alineación, horarios, reloj automático, trabajo en segundo plano y señales.
from PySide6.QtCore import Qt, QTime, QTimer, QThread, Signal, QSettings
# Elementos visuales para mostrar colores, texto con formato e imágenes.
from PySide6.QtGui import QColor, QFont, QPixmap
# Controles que forman la ventana: botones, tablas, campos de texto, avisos y paneles.
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QFrame, QTableWidget, QTableWidgetItem, QHeaderView,
    QLineEdit, QComboBox, QSpinBox, QTimeEdit, QMessageBox, QAbstractItemView,
    QFileDialog, QStackedWidget, QCheckBox, QSizePolicy, QScrollArea
)

# Funciones del lector físico: conectar con la cámara, procesar códigos QR y apagar sus luces.
from estacion import CameraError, EspCamClient, ScanProcessor, LED_APAGADO

# Lee opciones de un archivo `.env`; si no existe, el programa sigue usando valores predeterminados.
load_dotenv()

# Dirección del servidor local que almacena las clases, estudiantes y asistencias.
API_BASE = "http://127.0.0.1:8000"
# Dirección inicial de la ESP32-CAM. La que se escriba en la interfaz se recuerda.
ESP32_CAM_URL = os.getenv("ESP32_CAM_URL", "http://192.168.1.50")

# Colores de fondo y texto para que el resultado de la cámara sea fácil de distinguir.
STATION_COLORS = {
    "green": ("#DDF7E8", "#18794E"),
    "red": ("#FCE8E7", "#B42318"),
    "orange": ("#FFF1DB", "#B54708"),
}


class ApiError(Exception):
    """Error de comunicación que la interfaz puede explicar en una ventana de aviso."""
    # Es un tipo de error propio para reconocer cuando falla la comunicación con el servidor.
    pass


class StationWorker(QThread):
    """Hilo de la estación: pide fotos a la ESP32-CAM y procesa los QR.

    Corre aparte para que la ventana no se congele mientras espera la red.
    Se comunica con la interfaz solo mediante señales.
    """

    # Estas señales envían información desde el hilo de cámara hasta la ventana principal.
    frame_ready = Signal(bytes)          # Foto comprimida que se mostrará en la vista en vivo.
    scan_result = Signal(object)         # Resultado de leer y validar un código QR.
    camera_state = Signal(bool, str)     # Indica si hay conexión y contiene un mensaje explicativo.

    def __init__(self, camera_url, session_id, parent=None):
        """Prepara el lector de cámara y el procesador para una sesión activa."""
        super().__init__(parent)  # Inicializa el hilo de Qt y lo vincula con la ventana.
        self.camera = EspCamClient(camera_url)  # Prepara la conexión con la cámara indicada.
        self.processor = ScanProcessor(API_BASE, session_id)  # Prepara la lectura y validación de QR.
        self._stop = threading.Event()  # Bandera que permite pedir al hilo que termine.
        self.interval_s = 0.25  # Pausa entre lecturas para no solicitar fotos continuamente.

    def stop(self):
        """Pide al ciclo de lectura que termine de forma ordenada."""
        self._stop.set()  # Activa la bandera; el ciclo de lectura la comprobará y se detendrá.

    def run(self):
        """Lee fotos repetidamente, procesa sus QR y avisa cada resultado a la ventana."""
        connected = None  # Recuerda el estado anterior para avisar solo cuando haya cambios.
        while not self._stop.is_set():
            try:
            # Pide una fotografía a la cámara; si la conexión falla, pasa al bloque de error.
                jpeg = self.camera.capture()
            except CameraError as exc:
                if connected is not False:
                    self.camera_state.emit(False, str(exc))
                connected = False
                self._stop.wait(2.0)   # Espera dos segundos antes de reintentar la conexión.
                continue
            if connected is not True:
                self.camera_state.emit(True, f"Conectada en {self.camera.base_url}")
            connected = True
            self.frame_ready.emit(jpeg)  # Envía la fotografía a la ventana para actualizar la vista.
            try:
                # Busca un QR en la fotografía y solicita su validación para esta sesión.
                result = self.processor.process_frame(jpeg)
            except Exception as exc:  # noqa: BLE001 - la lectura no debe detenerse
                self.camera_state.emit(True, f"Error al procesar la foto: {exc}")
                result = None
            if result is not None:
                # Cambia la luz de la cámara y envía el resultado para presentarlo en pantalla.
                self.camera.led(result.led)
                self.scan_result.emit(result)
            self._stop.wait(self.interval_s)


class AulaCheckApp(QMainWindow):
    """Interfaz PySide6 conectada al backend FastAPI de AulaCheck."""

    def __init__(self):
        """Construye la ventana, sus páginas y la sincronización con el servidor."""
        super().__init__()  # Prepara la ventana principal de Qt.
        self.setWindowTitle("AulaCheck | Sistema de asistencia académica")
        self.resize(1360, 860)
        self.setMinimumSize(1120, 720)

        # Datos que la aplicación conserva en memoria mientras está abierta.
        self.classes = []  # Lista de clases obtenida del servidor.
        self.current_class_index = 0
        self.current_session_id = None
        self.session_active = False
        self.roster = []
        self.records = []
        self.station_worker = None
        self.settings = QSettings("AulaCheck", "Interfaz docente")  # Guarda opciones entre aperturas.

        # Apariencia general de la aplicación: colores, letras, botones, campos y tablas.
        self.setStyleSheet("""
            QMainWindow, QWidget { background:#F4F7FB; color:#172033; font-family:'Segoe UI'; }
            QLabel, QCheckBox { background:transparent; }
            QCheckBox::indicator { width:15px; height:15px; border:1px solid #98A2B3; border-radius:4px; background:white; }
            QCheckBox::indicator:checked { background:#3867E8; border-color:#3867E8; }
            QFrame#Sidebar { background:#152238; border-radius:16px; }
            QLabel#Brand { color:white; font-size:23px; font-weight:800; }
            QLabel#SideCaption { color:#9FAFC6; font-size:10px; font-weight:800; }
            QPushButton#Nav { text-align:left; color:#D8E1EF; background:transparent; border:none;
                padding:12px 13px; border-radius:9px; font-size:13px; }
            QPushButton#Nav:hover, QPushButton#Nav:checked { background:#263B59; color:white; }
            QLabel#PageTitle { font-size:27px; font-weight:800; color:#172033; }
            QLabel#Muted { color:#6B778C; font-size:12px; }
            QFrame#Card, QFrame#Panel { background:white; border:1px solid #E5EAF2; border-radius:14px; }
            QLabel#MetricTitle { color:#6B778C; font-size:12px; }
            QLabel#MetricValue { color:#172033; font-size:27px; font-weight:800; }
            QPushButton#Primary { background:#3867E8; color:white; border:none; border-radius:8px;
                padding:10px 14px; font-weight:700; }
            QPushButton#Primary:hover { background:#2C54C5; }
            QPushButton#Secondary { background:#EAF0FF; color:#315BD0; border:none; border-radius:8px;
                padding:9px 12px; font-weight:700; }
            QPushButton#Danger { background:#FCE8E7; color:#B42318; border:none; border-radius:8px;
                padding:10px 13px; font-weight:700; }
            QPushButton#Success { background:#DDF7E8; color:#18794E; border:none; border-radius:8px;
                padding:10px 13px; font-weight:700; }
            QPushButton#Running { background:#18794E; color:white; border:none; border-radius:8px;
                padding:10px 13px; font-weight:800; }
            QLineEdit, QComboBox, QSpinBox, QTimeEdit {
                background:white; border:1px solid #D8DFEA; border-radius:7px; padding:8px; min-height:18px;
            }
            QTableWidget { background:white; border:1px solid #D9E0EA; gridline-color:#C9D2E0;
                selection-background-color:#E8EEFF; selection-color:#172033; }
            QHeaderView::section { background:#F7F9FC; color:#53627A; border:1px solid #C9D2E0;
                padding:11px; font-weight:700; }
        """)

        # Contenedor raíz: organiza la barra lateral y el área principal.
        root = QWidget()  # Contenedor que agrupa la barra lateral y el contenido de cada página.
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(18, 18, 18, 18)
        root_layout.setSpacing(18)

        sidebar = QFrame()  # Panel lateral donde aparecen las opciones de navegación.
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(228)
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(16, 22, 16, 18)
        side.setSpacing(8)
        brand = QLabel("◈ AulaCheck")
        brand.setObjectName("Brand")
        side.addWidget(brand)
        tagline = QLabel("ASISTENCIA ACADÉMICA")
        tagline.setObjectName("SideCaption")
        side.addWidget(tagline)
        side.addSpacing(20)
        side.addWidget(self.section_label("MENÚ PRINCIPAL"))

        # Botones de navegación para cambiar entre panel, clases, historial y acerca de.
        self.nav_buttons = []  # Aquí se guardan los botones para poder marcar cuál está seleccionado.
        # Cada pareja contiene el texto de un botón y el número de la página que abre.
        for text, index in [
            ("▦   Panel de asistencia", 0),
            ("▣   Gestión de clases", 1),
            ("◷   Historial", 2),
            ("ⓘ   Acerca de", 3),
        ]:
            btn = QPushButton(text)
            btn.setObjectName("Nav")
            btn.setCheckable(True)
            # Al pulsarlo, llama a navigate con el número de página correspondiente.
            btn.clicked.connect(lambda checked=False, i=index: self.navigate(i))
            side.addWidget(btn)
            self.nav_buttons.append(btn)
        self.nav_buttons[0].setChecked(True)
        side.addStretch()

        device = QFrame()
        device.setStyleSheet("QFrame {background:#203550; border-radius:11px;}")
        dv = QVBoxLayout(device)
        dv.setContentsMargins(12, 12, 12, 12)
        d1 = QLabel("ESTACIÓN DE LECTURA")
        d1.setStyleSheet("color:#9FAFC6;font-size:10px;font-weight:800;")
        self.device_status = QLabel("●  ESP32-CAM no conectada")
        self.device_status.setStyleSheet("color:#F6D98B;font-size:12px;font-weight:700;")
        d2 = QLabel("Backend conectado por HTTP")
        d2.setStyleSheet("color:#D8E1EF;font-size:11px;")
        dv.addWidget(d1)
        dv.addWidget(self.device_status)
        dv.addWidget(d2)
        side.addWidget(device)

        main_area = QWidget()
        main_layout = QVBoxLayout(main_area)
        main_layout.setContentsMargins(0, 0, 0, 0)
        self.stack = QStackedWidget()  # Permite guardar varias páginas y mostrar solo una a la vez.
        self.stack.addWidget(self.build_dashboard())
        self.stack.addWidget(self.build_classes_page())
        self.stack.addWidget(self.build_history_page())
        self.stack.addWidget(self.build_about_page())
        main_layout.addWidget(self.stack)
        root_layout.addWidget(sidebar)
        root_layout.addWidget(main_area, 1)
        self.setCentralWidget(root)

        # Carga inicial: rellena la interfaz con los datos actuales del backend.
        self.load_classes(show_errors=False)  # Carga las clases sin mostrar una alerta al iniciar.
        self.refresh_history()  # Carga también la lista de sesiones anteriores.

        # Actualización automática cada 30 segundos.
        # QTimer ejecuta el método dentro del ciclo de eventos de Qt, sin bloquear la ventana.
        self.refresh_timer = QTimer(self)  # Reloj que vuelve a consultar los datos cada cierto tiempo.
        self.refresh_timer.setInterval(30_000)  # 30.000 milisegundos = 30 segundos.
        self.refresh_timer.timeout.connect(self.refresh_automatically)
        self.refresh_timer.start()

    # ---------- API helpers: comunicación HTTP con el backend FastAPI ----------
    def api(self, method, path, **kwargs):
        """Realiza una petición HTTP y convierte errores de red/API en ApiError."""
        try:
            # Envía una solicitud al servidor; el método puede ser GET, POST o PATCH, entre otros.
            response = requests.request(method, f"{API_BASE}{path}", timeout=5, **kwargs)
        except requests.RequestException as exc:
            raise ApiError(
                "No se pudo conectar con FastAPI.\n"
                "Comprueba que el backend esté ejecutándose en http://127.0.0.1:8000.\n\n"
                f"Detalle: {exc}"
            )
        # Si el servidor indica un fallo, obtiene el detalle para mostrarlo en un aviso.
        if not response.ok:
            try:
                detail = response.json().get("detail", response.text)
            except ValueError:
                detail = response.text
            raise ApiError(f"Error HTTP {response.status_code}: {detail}")
        # Algunos mensajes de éxito no traen datos; en ese caso se devuelve `None`.
        if response.status_code == 204 or not response.content:
            return None
        # Convierte la respuesta JSON del servidor en datos que Python puede utilizar.
        return response.json()

    def run_action(self, action, success_message=None):
        """Ejecuta una acción y muestra confirmaciones o errores al docente."""
        # Intenta hacer la acción y muestra un aviso distinto si ocurre un error.
        try:
            result = action()
            if success_message:
                QMessageBox.information(self, "AulaCheck", success_message)
            return result
        except ApiError as exc:
            QMessageBox.warning(self, "No se pudo completar la operación", str(exc))
        except (ValueError, KeyError, TypeError) as exc:
            QMessageBox.critical(self, "Error inesperado", str(exc))
        return None

    def current_class(self):
        """Devuelve la clase seleccionada, ajustando el índice si cambió la lista."""
        # Si no hay clases cargadas, no existe una clase actual que devolver.
        if not self.classes:
            return None
        # Corrige el número seleccionado si la lista se redujo desde la última consulta.
        self.current_class_index = max(0, min(self.current_class_index, len(self.classes) - 1))
        return self.classes[self.current_class_index]

    def current_nrc(self):
        """Devuelve el código de la clase actual o `None` si no hay una seleccionada."""
        c = self.current_class()
        return c["nrc"] if c else None

    # ---------- UI helpers ----------
    def section_label(self, text):
        """Crea un rótulo pequeño para separar grupos de opciones en la ventana."""
        l = QLabel(text)
        l.setStyleSheet("font-size:11px;font-weight:800;color:#6B778C;letter-spacing:1px;")
        return l

    def panel(self):
        """Crea un contenedor con el estilo visual usado para los paneles."""
        f = QFrame()
        f.setObjectName("Panel")
        return f

    def page_header(self, title, subtitle):
        """Prepara el título, la explicación y la fecha de una página."""
        # Coloca el título y subtítulo a la izquierda y la fecha a la derecha.
        row = QHBoxLayout()
        col = QVBoxLayout()
        t = QLabel(title)
        t.setObjectName("PageTitle")
        s = QLabel(subtitle)
        s.setObjectName("Muted")
        col.addWidget(t)
        col.addWidget(s)
        row.addLayout(col)
        row.addStretch()
        row.addWidget(QLabel(datetime.now().strftime("%d/%m/%Y")))
        return row

    def metric_card(self, title, value):
        """Construye una tarjeta que muestra una cifra resumida del panel."""
        card = QFrame()
        card.setObjectName("Card")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(15, 13, 15, 13)
        t = QLabel(title)
        t.setObjectName("MetricTitle")
        v = QLabel(str(value))
        v.setObjectName("MetricValue")
        lay.addWidget(t)
        lay.addWidget(v)
        card.value_label = v
        return card

    def setup_table(self, table):
        """Configura una tabla de solo lectura que selecciona filas completas."""
        # Activa las líneas, permite seleccionar filas completas y prohíbe editar las celdas.
        table.setShowGrid(True)
        table.setGridStyle(Qt.SolidLine)
        table.verticalHeader().setVisible(False)
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setSelectionMode(QAbstractItemView.SingleSelection)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.setWordWrap(False)

    # ---------- Pages ----------
    def build_dashboard(self):
        """Construye el panel principal de asistencia, indicadores y controles de sesión."""
        # La página se arma con controles de clase, indicadores, lista de alumnos y botones.
        page = QWidget()  # Crea la página principal con resumen y controles de asistencia.
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)
        layout.addLayout(self.page_header("Panel de asistencia", "Sesiones reales guardadas en MySQL mediante FastAPI."))

        # Esta franja permite elegir una clase y revisar o guardar su hora de inicio y tolerancia.
        config = self.panel()
        cg = QGridLayout(config)
        cg.setContentsMargins(16, 13, 16, 13)
        cg.setSpacing(10)
        cg.addWidget(self.section_label("INFORMACIÓN DE LA CLASE"), 0, 0, 1, 5)
        # Menú para escoger una clase; al cambiar la selección se actualiza el panel.
        self.course_combo = QComboBox()
        self.course_combo.currentIndexChanged.connect(self.on_dashboard_class_changed)
        self.start_time_label = QLabel("—")
        self.start_time_label.setStyleSheet("font-size:14px;font-weight:700;color:#344054;padding:7px;")
        # Selector numérico para indicar cuántos minutos de retraso se permiten.
        self.tolerance = QSpinBox()
        self.tolerance.setRange(0, 180)
        self.tolerance.setSuffix(" min")
        cg.addWidget(QLabel("Asignatura / NRC"), 1, 0)
        cg.addWidget(self.course_combo, 2, 0, 1, 2)
        cg.addWidget(QLabel("Hora de inicio (solo lectura)"), 1, 2)
        cg.addWidget(self.start_time_label, 2, 2)
        cg.addWidget(QLabel("Tolerancia ajustable"), 1, 3)
        cg.addWidget(self.tolerance, 2, 3)
        self.save_config_btn = QPushButton("Guardar tolerancia")
        self.save_config_btn.setObjectName("Secondary")
        self.save_config_btn.clicked.connect(self.save_tolerance)
        cg.addWidget(self.save_config_btn, 2, 4)
        layout.addWidget(config)

        # Cuatro tarjetas resumen muestran cuántos alumnos hay en cada estado.
        cards = QHBoxLayout()
        self.metric_total = self.metric_card("Estudiantes de la clase", 0)
        self.metric_present = self.metric_card("Asistencia válida", 0)
        self.metric_late = self.metric_card("Tarde / ausente", 0)
        self.metric_pending = self.metric_card("Pendientes", 0)
        for c in [self.metric_total, self.metric_present, self.metric_late, self.metric_pending]:
            cards.addWidget(c)
        layout.addLayout(cards)

        # La tabla principal permite buscar alumnos y consultar cada resultado de asistencia.
        table_panel = self.panel()
        tp = QVBoxLayout(table_panel)
        tp.setContentsMargins(15, 13, 15, 14)
        header = QHBoxLayout()
        header.addWidget(self.section_label("LISTA DE ASISTENCIA"))
        header.addStretch()
        self.search_attendance = QLineEdit()
        self.search_attendance.setPlaceholderText("Buscar estudiante...")
        self.search_attendance.setMaximumWidth(220)
        self.search_attendance.textChanged.connect(self.render_attendance_table)
        header.addWidget(self.search_attendance)
        tp.addLayout(header)

        # Tabla vacía con cuatro columnas para nombre, correo, hora de registro y estado.
        self.attendance_table = QTableWidget(0, 4)
        self.attendance_table.setHorizontalHeaderLabels(["Nombre del estudiante", "Correo institucional", "Hora de registro", "Estado"])
        self.attendance_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.attendance_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.attendance_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.attendance_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.setup_table(self.attendance_table)
        tp.addWidget(self.attendance_table, 1)

        # Estos botones abren y cierran la sesión, agregan registros y exportan la lista.
        actions = QHBoxLayout()
        self.session_label = QLabel("● Sesión no iniciada")
        self.session_label.setStyleSheet("color:#6B778C;font-weight:700;")
        self.session_label.setWordWrap(True)
        self.session_label.setMinimumWidth(140)
        actions.addWidget(self.session_label)
        actions.addStretch()
        # Botones para iniciar, terminar, registrar manualmente, exportar y actualizar datos.
        self.start_btn = QPushButton("▶  Iniciar asistencia")
        self.start_btn.setObjectName("Success")
        self.start_btn.clicked.connect(self.start_session)
        self.finish_btn = QPushButton("■  Finalizar clase")
        self.finish_btn.setObjectName("Danger")
        self.finish_btn.clicked.connect(self.finish_session)
        self.finish_btn.setEnabled(False)
        self.manual_btn = QPushButton("＋ Añadir asistencia")
        self.manual_btn.setObjectName("Secondary")
        self.manual_btn.clicked.connect(self.manual_attendance)
        self.export_btn = QPushButton("⇩  Guardar / exportar")
        self.export_btn.setObjectName("Primary")
        self.export_btn.clicked.connect(self.export_attendance)
        self.refresh_btn = QPushButton("↻ Actualizar")
        self.refresh_btn.setObjectName("Secondary")
        self.refresh_btn.clicked.connect(self.refresh_dashboard_data)
        for b in [self.start_btn, self.finish_btn, self.manual_btn, self.export_btn, self.refresh_btn]:
            # Los botones no se encogen por debajo de su texto; el texto de la sesión sí.
            b.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
            actions.addWidget(b)
        body = QHBoxLayout()
        body.setSpacing(14)
        body.addWidget(table_panel, 1)
        body.addWidget(self.build_station_panel())
        layout.addLayout(body, 1)

        # Botones de la sesión en una barra propia, a lo ancho de la página.
        actions_panel = self.panel()
        actions.setContentsMargins(15, 10, 15, 10)
        actions_panel.setLayout(actions)
        layout.addWidget(actions_panel)
        return page

    def build_station_panel(self):
        """Construye los controles para conectar, probar y ver la estación de lectura."""
        # Este panel concentra la dirección de la cámara, una vista previa y los controles de luz.
        """Panel de la estación ESP32-CAM: dirección, vista en vivo y última lectura."""
        # Panel para configurar la cámara y ver su imagen y el último QR leído.
        panel = self.panel()
        panel.setFixedWidth(350)
        outer = QVBoxLayout(panel)
        outer.setContentsMargins(1, 1, 1, 1)
        # Si la ventana es baja, el panel se desplaza en lugar de encimar elementos.
        scroll = QScrollArea()  # Añade desplazamiento si el panel no cabe en el espacio disponible.
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea, QScrollArea > QWidget > QWidget { background:white; border:none; }")
        content = QWidget()
        scroll.setWidget(content)
        outer.addWidget(scroll)
        lay = QVBoxLayout(content)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(7)
        lay.addWidget(self.section_label("ESTACIÓN ESP32-CAM"))

        # El campo guarda la dirección de red de la ESP32-CAM.
        url_row = QHBoxLayout()
        # Muestra la dirección guardada de la cámara o, si no hay una, la dirección predeterminada.
        self.station_url_input = QLineEdit(self.settings.value("station_url", ESP32_CAM_URL))
        self.station_url_input.setPlaceholderText("IP de la cámara, ej. 192.168.1.50")
        self.station_url_input.setToolTip(
            "Dirección de la ESP32-CAM. La muestra el Serial Monitor de Arduino IDE al encender la placa."
        )
        self.station_url_input.editingFinished.connect(self.save_station_url)
        test_btn = QPushButton("Probar")
        test_btn.setObjectName("Secondary")
        test_btn.clicked.connect(self.test_station)
        url_row.addWidget(self.station_url_input, 1)
        url_row.addWidget(test_btn)
        lay.addLayout(url_row)

        # Esta etiqueta se reemplaza por la foto más reciente cuando la cámara responde.
        self.station_preview = QLabel("Sin imagen.\nPulse «Probar» o inicie la asistencia.")
        self.station_preview.setAlignment(Qt.AlignCenter)
        # La vista se adapta al alto disponible (mínimo 192x144, máximo 316x237).
        self.station_preview.setMinimumSize(192, 144)
        self.station_preview.setMaximumSize(316, 237)
        self.station_preview.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.station_preview.setStyleSheet(
            "background:#0F172A;color:#9FAFC6;border-radius:10px;font-size:12px;"
        )
        lay.addWidget(self.station_preview, 1, Qt.AlignHCenter)

        # Controles de luz y mensajes del último QR leído.
        tools = QHBoxLayout()
        self.flash_check = QCheckBox("Flash")
        self.flash_check.toggled.connect(self.toggle_flash)
        led_btn = QPushButton("Probar LED")
        led_btn.setObjectName("Secondary")
        led_btn.clicked.connect(self.test_station_leds)
        tools.addWidget(self.flash_check)
        tools.addStretch()
        tools.addWidget(led_btn)
        lay.addLayout(tools)

        self.station_state_label = QLabel("● Lectura detenida")
        self.station_state_label.setStyleSheet("color:#6B778C;font-weight:700;")
        self.station_state_label.setWordWrap(True)
        lay.addWidget(self.station_state_label)

        lay.addWidget(self.section_label("ÚLTIMA LECTURA"))
        self.station_result = QLabel("Todavía no se ha leído ningún QR.")
        self.station_result.setWordWrap(True)
        self.station_result.setMinimumHeight(54)
        self.station_result.setStyleSheet(
            "background:#EDF0F5;color:#596579;border-radius:10px;padding:10px;font-size:12px;"
        )
        lay.addWidget(self.station_result)
        return panel

    def build_classes_page(self):
        """Construye el formulario y las tablas para crear clases y matricular estudiantes."""
        # Incluye un formulario de clase, la lista de clases y la lista de estudiantes inscritos.
        """Construye la pantalla para crear clases y gestionar estudiantes vinculados."""
        page = QWidget()  # Página para crear clases y administrar la lista de estudiantes.
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)
        layout.addLayout(self.page_header("Gestión de clases", "Crea clases en MySQL y vincula estudiantes existentes por correo institucional."))

        # Formulario superior: nombre de clase, hora, margen permitido y botón para crearla.
        form = self.panel()
        grid = QGridLayout(form)
        grid.setContentsMargins(18, 18, 18, 18)
        grid.setSpacing(10)
        grid.addWidget(self.section_label("CREAR NUEVA CLASE"), 0, 0, 1, 4)
        self.new_class_name = QLineEdit()
        self.new_class_name.setPlaceholderText("Ej. Computación e Interfaces")
        self.new_class_start = QTimeEdit()
        self.new_class_start.setDisplayFormat("HH:mm")
        self.new_class_start.setTime(QTime(8, 0))
        self.new_class_tolerance = QSpinBox()
        self.new_class_tolerance.setRange(0, 180)
        self.new_class_tolerance.setValue(10)
        self.new_class_tolerance.setSuffix(" min")
        grid.addWidget(QLabel("Nombre de la clase"), 1, 0)
        grid.addWidget(self.new_class_name, 2, 0, 1, 2)
        grid.addWidget(QLabel("Hora de inicio"), 1, 2)
        grid.addWidget(self.new_class_start, 2, 2)
        grid.addWidget(QLabel("Tolerancia inicial"), 1, 3)
        grid.addWidget(self.new_class_tolerance, 2, 3)
        create_btn = QPushButton("Crear clase y generar NRC")
        create_btn.setObjectName("Primary")
        create_btn.clicked.connect(self.create_class)
        grid.addWidget(create_btn, 2, 4)
        layout.addWidget(form)

        # La tabla central permite seleccionar una clase para ver o actualizar su matrícula.
        classes_panel = self.panel()
        cl = QVBoxLayout(classes_panel)
        cl.setContentsMargins(16, 14, 16, 14)
        cl.addWidget(self.section_label("CLASES REGISTRADAS — SELECCIONA UNA PARA ADMINISTRAR SU LISTA"))
        self.classes_table = QTableWidget(0, 5)
        self.classes_table.setHorizontalHeaderLabels(["NRC", "Asignatura", "Hora de inicio", "Tolerancia", "Estudiantes"])
        self.classes_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.classes_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        for i in [2, 3, 4]:
            self.classes_table.horizontalHeader().setSectionResizeMode(i, QHeaderView.ResizeToContents)
        self.setup_table(self.classes_table)
        self.classes_table.itemSelectionChanged.connect(self.refresh_roster_for_selected_class)
        cl.addWidget(self.classes_table)
        layout.addWidget(classes_panel, 1)

        # La sección inferior agrega alumnos por correo y muestra quiénes están vinculados.
        roster_panel = self.panel()
        rl = QVBoxLayout(roster_panel)
        rl.setContentsMargins(16, 14, 16, 14)
        self.roster_heading = QLabel("Estudiantes vinculados a la clase seleccionada")
        self.roster_heading.setStyleSheet("font-size:15px;font-weight:800;color:#17365D;")
        rl.addWidget(self.roster_heading)
        note = QLabel("Solo se vinculan correos que ya existan en la tabla estudiantes de MySQL.")
        note.setObjectName("Muted")
        rl.addWidget(note)
        addrow = QHBoxLayout()
        self.student_email_input = QLineEdit()
        self.student_email_input.setPlaceholderText("nombre.apellido@utb.edu.co")
        self.student_email_input.returnPressed.connect(self.enroll_student)
        self.add_student_btn = QPushButton("＋ Añadir por correo")
        self.add_student_btn.setObjectName("Secondary")
        self.add_student_btn.clicked.connect(self.enroll_student)
        addrow.addWidget(self.student_email_input, 1)
        addrow.addWidget(self.add_student_btn)
        rl.addLayout(addrow)
        self.class_roster_table = QTableWidget(0, 2)
        self.class_roster_table.setHorizontalHeaderLabels(["Nombre del estudiante", "Correo institucional"])
        self.class_roster_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.class_roster_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.setup_table(self.class_roster_table)
        rl.addWidget(self.class_roster_table)
        layout.addWidget(roster_panel, 1)
        return page

    def build_history_page(self):
        """Construye la tabla donde se consultan las sesiones pasadas y actuales."""
        # El historial resume cuándo se abrió y cerró cada sesión de clase.
        """Construye la tabla con el historial de sesiones de asistencia."""
        page = QWidget()  # Página que muestra las sesiones pasadas y su estado.
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)
        layout.addLayout(self.page_header("Historial de asistencia", "Sesiones consultadas directamente desde FastAPI y MySQL."))
        panel = self.panel()
        pl = QVBoxLayout(panel)
        pl.setContentsMargins(16, 16, 16, 16)
        pl.addWidget(self.section_label("SESIONES REGISTRADAS"))
        self.history_table = QTableWidget(0, 5)
        self.history_table.setHorizontalHeaderLabels(["ID sesión", "NRC", "Inicio", "Finalización", "Estado"])
        self.history_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.history_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.history_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.history_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.history_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.setup_table(self.history_table)
        pl.addWidget(self.history_table)
        refresh = QPushButton("↻ Actualizar historial")
        refresh.setObjectName("Secondary")
        refresh.clicked.connect(self.refresh_history)
        pl.addWidget(refresh, alignment=Qt.AlignRight)
        layout.addWidget(panel, 1)
        return page

    def build_about_page(self):
        """Construye la página con información general del sistema."""
        # Presenta el propósito del sistema y las partes que colaboran durante el registro.
        """Construye la pantalla informativa del proyecto y sus integrantes."""
        page = QWidget()  # Página informativa sobre el proyecto y sus integrantes.
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)
        layout.addLayout(self.page_header("Acerca del proyecto", "Quiénes somos, qué hacemos y qué valor aportamos."))
        panel = self.panel()
        pl = QVBoxLayout(panel)
        pl.setContentsMargins(26, 24, 26, 24)
        pl.setSpacing(12)
        title = QLabel("AulaCheck · Asistencia académica mediante códigos QR")
        title.setStyleSheet("font-size:20px;font-weight:800;color:#17365D;")
        pl.addWidget(title)
        desc = QLabel(
            "Somos un equipo de estudiantes que integra programación, interfaces y electrónica para facilitar "
            "el registro de asistencia. La propuesta combina Flutter para mostrar el QR de cada estudiante, ESP32-CAM "
            "para capturarlo por WiFi, OpenCV para leerlo, FastAPI para validar la solicitud, MySQL para almacenar los datos y PySide6 "
            "para que el profesor gestione las clases y consulte los resultados."
        )
        desc.setWordWrap(True)
        pl.addWidget(desc)
        pl.addWidget(self.section_label("INTEGRANTES"))
        for name in ["Fredy Jarava Chavez", "Jerry Buelvas Mejia", "Juan Caicedo Gomez", "Rafael Villero Castillo"]:
            pl.addWidget(QLabel("•  " + name))
        pl.addStretch()
        layout.addWidget(panel, 1)
        return page

    # ---------- Estación ESP32-CAM ----------
    def station_url(self):
        """Lee la dirección escrita o guardada de la cámara."""
        # `strip` quita espacios accidentales al principio y al final de la dirección.
        return self.station_url_input.text().strip()

    def save_station_url(self):
        """Guarda la dirección de cámara para recuperarla cuando se reabra la app."""
        # Conserva la dirección para que no haya que escribirla cada vez que se abre la aplicación.
        self.settings.setValue("station_url", self.station_url())

    def set_device_status(self, text, ok):
        """Actualiza el aviso lateral que indica si la estación está conectada."""
        self.device_status.setText(f"●  {text}")
        color = "#8DE0B0" if ok else "#F6D98B"
        self.device_status.setStyleSheet(f"color:{color};font-size:12px;font-weight:700;")

    def set_station_state(self, text, color="#6B778C", detail=""):
        """Cambia el mensaje de estado y guarda una explicación emergente."""
        self.station_state_label.setText(f"● {text}")
        self.station_state_label.setToolTip(detail or text)
        self.station_state_label.setStyleSheet(f"color:{color};font-weight:700;")

    def show_station_frame(self, jpeg):
        """Muestra en la ventana la última foto recibida desde la cámara."""
        # Prepara una imagen de Qt y carga en ella los bytes recibidos desde la cámara.
        pixmap = QPixmap()
        if pixmap.loadFromData(jpeg, "JPG"):
            self.station_preview.setPixmap(pixmap.scaled(
                self.station_preview.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
            ))

    def test_station(self):
        """Comprueba la conexión con la ESP32-CAM y muestra una foto."""
        self.save_station_url()
        if self.station_worker is not None:
            QMessageBox.information(self, "Estación", "La estación ya está leyendo; mire la vista en vivo.")
            return
        # Crea una conexión temporal para comprobar la cámara sin iniciar la lectura continua.
        camera = EspCamClient(self.station_url())
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            status = camera.status()
            if not status.get("camera"):
                raise CameraError(
                    f'La placa responde, pero la cámara no inició (código {status.get("camera_error")}). '
                    "Revise el cable plano y pulse RST."
                )
            self.show_station_frame(camera.capture())
            self.set_station_state(f'Cámara lista · señal {status.get("rssi", "?")} dBm', "#18794E",
                                   f'Conectada en {camera.base_url}')
            self.set_device_status("ESP32-CAM conectada", True)
        except CameraError as exc:
            self.set_station_state("Sin conexión con la cámara", "#B42318", str(exc))
            self.set_device_status("ESP32-CAM no conectada", False)
            QApplication.restoreOverrideCursor()
            QMessageBox.warning(self, "No se pudo conectar con la ESP32-CAM", str(exc))
            return
        QApplication.restoreOverrideCursor()

    def test_station_leds(self):
        """Envía una orden de prueba para comprobar las luces de la cámara."""
        if not EspCamClient(self.station_url()).led("test"):
            QMessageBox.warning(self, "Estación", "No se pudo contactar a la ESP32-CAM para probar los LED.")

    def toggle_flash(self, on):
        """Enciende o apaga la luz auxiliar y revierte la casilla si falla."""
        if not EspCamClient(self.station_url()).flash(on):
            self.flash_check.blockSignals(True)
            self.flash_check.setChecked(False)
            self.flash_check.blockSignals(False)
            QMessageBox.warning(self, "Estación", "No se pudo contactar a la ESP32-CAM para cambiar el flash.")

    def start_station(self, show_errors=True):
        """Arranca la lectura de QR para la sesión activa."""
        if self.station_worker is not None or self.current_session_id is None:
            return False
        if not self.station_url():
            if show_errors:
                QMessageBox.warning(self, "Estación sin dirección",
                                    "Escriba la dirección de la ESP32-CAM en el panel de la estación.")
            return False
        self.save_station_url()
        # Crea un hilo independiente para que leer la cámara no bloquee los controles de la ventana.
        worker = StationWorker(self.station_url(), self.current_session_id, self)
        worker.frame_ready.connect(self.show_station_frame)
        worker.scan_result.connect(self.on_station_result)
        worker.camera_state.connect(self.on_station_camera_state)
        worker.finished.connect(worker.deleteLater)
        self.station_worker = worker
        self.station_url_input.setEnabled(False)
        self.set_station_state("Conectando con la cámara…", "#B54708")
        worker.start()
        return True

    def stop_station(self, turn_off_leds=True):
        """Detiene el lector, espera que termine y opcionalmente apaga las luces."""
        # Recupera el hilo activo; si no existe, no hay nada que detener.
        worker = self.station_worker
        if worker is None:
            return
        self.station_worker = None
        worker.stop()
        worker.wait(6000)
        if turn_off_leds:
            EspCamClient(self.station_url(), timeout=1.5).led(LED_APAGADO)
        self.station_url_input.setEnabled(True)
        self.set_station_state("Lectura detenida")
        self.set_device_status("Estación detenida", False)

    def on_station_camera_state(self, connected, message):
        """Refleja si la cámara se conectó o está intentando reconectarse."""
        if connected:
            self.set_station_state("Leyendo QR", "#18794E", message)
            self.set_device_status("ESP32-CAM leyendo QR", True)
        else:
            # Mensaje corto en el panel; el detalle completo al pasar el mouse.
            self.set_station_state("Sin conexión con la cámara · reintentando", "#B42318", message)
            self.set_device_status("ESP32-CAM sin conexión", False)

    def on_station_result(self, result):
        """Muestra el resultado del QR y vuelve a cargar las asistencias."""
        bg, fg = STATION_COLORS.get(result.led, ("#EDF0F5", "#596579"))
        who = result.estudiante or result.email
        hour = datetime.now().strftime("%H:%M:%S")
        self.station_result.setText(f"<b>{result.titulo}</b> · {hour}<br>{who}<br><small>{result.detalle}</small>")
        self.station_result.setStyleSheet(
            f"background:{bg};color:{fg};border-radius:10px;padding:10px;font-size:12px;"
        )
        if self.current_session_id is not None:
            try:
                self.records = self.api("GET", f"/sessions/{self.current_session_id}/attendance")
                self.render_attendance_table()
            except ApiError:
                pass

    def closeEvent(self, event):
        """Detiene la cámara antes de cerrar la ventana."""
        self.stop_station()
        super().closeEvent(event)

    # ---------- Carga y sincronización de datos desde FastAPI ----------
    def load_classes(self, show_errors=True):
        """Carga clases y sincroniza selectores, panel principal e historial."""
        # Pide al servidor la lista de clases y actualiza las partes de la pantalla que dependen de ella.
        try:
            self.classes = self.api("GET", "/classes")
        except ApiError as exc:
            if show_errors:
                QMessageBox.warning(self, "Error al cargar clases", str(exc))
            self.classes = []
        if self.current_class_index >= len(self.classes):
            self.current_class_index = max(0, len(self.classes) - 1)
        self.populate_class_selectors()
        self.populate_classes_table()
        if self.classes:
            self.load_dashboard_class()
            self.refresh_roster_for_selected_class()
        else:
            self.roster = []
            self.records = []
            self.render_attendance_table()
            self.class_roster_table.setRowCount(0)
            self.start_time_label.setText("—")
            self.session_label.setText("● Crea o selecciona una clase")
        self.refresh_history()

    def populate_class_selectors(self):
        """Rellena el menú desplegable con las clases guardadas en el servidor."""
        # Evita que rellenar el menú se interprete como una selección hecha por la persona.
        self.course_combo.blockSignals(True)
        self.course_combo.clear()
        for c in self.classes:
            self.course_combo.addItem(f'{c["name"]} · NRC {c["nrc"]}')
        if self.classes:
            self.course_combo.setCurrentIndex(self.current_class_index)
        self.course_combo.blockSignals(False)

    def populate_classes_table(self):
        """Dibuja una fila por clase con su hora, tolerancia y cantidad de alumnos."""
        self.classes_table.blockSignals(True)
        self.classes_table.setRowCount(len(self.classes))
        for r, c in enumerate(self.classes):
            values = [c["nrc"], c["name"], str(c["start_time"])[:5], f'{c["tolerance_minutes"]} min', str(c["student_count"])]
            for col, value in enumerate(values):
                self.classes_table.setItem(r, col, QTableWidgetItem(value))
        if self.classes:
            self.classes_table.selectRow(self.current_class_index)
        self.classes_table.blockSignals(False)

    def load_dashboard_class(self):
        """Carga los datos de la clase elegida en el panel de asistencia."""
        c = self.current_class()
        if not c:
            return
        self.start_time_label.setText(str(c["start_time"])[:5])
        self.tolerance.setValue(int(c["tolerance_minutes"]))
        self.load_roster_and_records()

    def load_roster_and_records(self):
        """Obtiene los estudiantes de la clase y las asistencias de la sesión actual."""
        # Busca estudiantes de la clase actual y, si hay sesión abierta, también sus asistencias.
        c = self.current_class()
        if not c:
            self.roster, self.records = [], []
            self.render_attendance_table()
            return
        try:
            self.roster = self.api("GET", f'/classes/{c["nrc"]}/students')
            self.records = []
            if self.current_session_id is not None:
                self.records = self.api("GET", f"/sessions/{self.current_session_id}/attendance")
        except ApiError as exc:
            QMessageBox.warning(self, "No se pudieron cargar los datos", str(exc))
            self.roster, self.records = [], []
        self.render_attendance_table()

    def refresh_dashboard_data(self):
        """Vuelve a solicitar clases y estudiantes para actualizar el panel."""
        self.load_classes()
        if self.current_session_id is not None:
            self.load_roster_and_records()

    def refresh_automatically(self):
        """
        Sincroniza periódicamente la pantalla con FastAPI/MySQL.

        Se consulta de nuevo la lista de clases, el listado de estudiantes de la
        clase seleccionada, los registros de la sesión seleccionada y el historial.
        Los errores se ignoran silenciosamente en esta tarea periódica para evitar
        que aparezca una ventana emergente cada 30 segundos si el backend se cae.
        La siguiente actualización volverá a intentarlo.
        """
        try:
            # Recordar el NRC seleccionado para no cambiar de clase si la lista cambia.
            # Recuerda qué clase estaba seleccionada para conservarla al actualizar la lista.
            selected_class = self.current_class()
            selected_nrc = selected_class.get("nrc") if selected_class else None

            # Recargar clases desde la API.
            latest_classes = self.api("GET", "/classes")
            self.classes = latest_classes

            # Mantener seleccionada la misma clase por NRC, si todavía existe.
            if selected_nrc is not None:
                for index, item in enumerate(self.classes):
                    if str(item.get("nrc")) == str(selected_nrc):
                        self.current_class_index = index
                        break
                else:
                    self.current_class_index = 0
            elif self.classes:
                self.current_class_index = min(
                    self.current_class_index, len(self.classes) - 1
                )

            # Refrescar los selectores y la tabla de gestión sin perder la selección.
            self.populate_class_selectors()
            self.populate_classes_table()

            # Actualizar estudiantes y asistencias de la clase seleccionada.
            current = self.current_class()
            if current:
                self.start_time_label.setText(str(current.get("start_time", "—"))[:5])
                self.tolerance.blockSignals(True)
                self.tolerance.setValue(int(current.get("tolerance_minutes", 0)))
                self.tolerance.blockSignals(False)

                self.roster = self.api("GET", f'/classes/{current["nrc"]}/students')

                # Detectar también sesiones iniciadas fuera de PySide6 (por ejemplo, desde /docs).
                # Si hay una sesión activa para el NRC seleccionado, usar su ID para leer asistencias.
                # Consulta las sesiones de la clase para detectar una iniciada desde otra herramienta.
                sessions = self.api("GET", "/sessions", params={"nrc": current["nrc"]})
                active_session = next(
                    (session for session in reversed(sessions)
                     if session.get("status") == "active"),
                    None
                )
                if active_session is not None:
                    self.current_session_id = active_session["id"]
                    self.session_active = True
                    self.session_label.setText(
                        f'● Sesión activa · ID {self.current_session_id}'
                    )
                    self.session_label.setStyleSheet("color:#18794E;font-weight:700;")
                    self.start_btn.setText("●  Sesión en curso")
                    self.start_btn.setObjectName("Running")
                    self.start_btn.setEnabled(False)
                    self.finish_btn.setEnabled(True)
                    self.start_station(show_errors=False)

                if self.current_session_id is not None:
                    self.records = self.api(
                        "GET", f"/sessions/{self.current_session_id}/attendance"
                    )
                else:
                    self.records = []

                # Actualizar tabla principal, indicadores y tabla de estudiantes.
                self.render_attendance_table()
                self.refresh_roster_for_selected_class()

            # Refrescar el historial para reflejar sesiones iniciadas/finalizadas externamente.
            self.refresh_history()

        except (ApiError, KeyError, ValueError, TypeError):
            # No interrumpir la experiencia del usuario por un fallo temporal de conexión.
            # Las acciones manuales seguirán mostrando sus propios errores.
            return

    def navigate(self, index):
        """Cambia de sección y actualiza los datos correspondientes a esa pantalla."""
        if self.session_active and index == 1:
            QMessageBox.information(self, "Sesión activa", "Finaliza la sesión antes de gestionar las clases.")
            return
        # Muestra la página indicada y actualiza cuál botón de navegación aparece seleccionado.
        self.stack.setCurrentIndex(index)
        for i, b in enumerate(self.nav_buttons):
            b.setChecked(i == index)
        if index == 0:
            self.load_classes()
        elif index == 1:
            self.load_classes()
        elif index == 2:
            self.refresh_history()

    def on_dashboard_class_changed(self, index):
        """Gestiona el cambio de clase desde el selector del panel principal."""
        if index < 0 or index >= len(self.classes):
            return
        if self.session_active:
            QMessageBox.warning(self, "Sesión activa", "Finaliza la sesión antes de cambiar de clase.")
            self.course_combo.blockSignals(True)
            self.course_combo.setCurrentIndex(self.current_class_index)
            self.course_combo.blockSignals(False)
            return
        # Guarda la nueva selección y olvida la sesión anterior porque pertenece a otra clase.
        self.current_class_index = index
        self.current_session_id = None
        self.session_label.setText("● Sesión no iniciada")
        self.session_label.setStyleSheet("color:#6B778C;font-weight:700;")
        self.start_btn.setText("▶  Iniciar asistencia")
        self.start_btn.setObjectName("Success")
        self.start_btn.setStyleSheet("")
        self.start_btn.setEnabled(True)
        self.finish_btn.setEnabled(False)
        self.load_dashboard_class()
        self.populate_classes_table()
        self.refresh_roster_for_selected_class()

    def selected_class_table_index(self):
        """Devuelve la fila elegida o indica que no existe una selección válida."""
        row = self.classes_table.currentRow()
        if row < 0 or row >= len(self.classes):
            return None
        return row

    def refresh_roster_for_selected_class(self):
        """Actualiza la lista de estudiantes vinculados en la sección de gestión."""
        if not hasattr(self, "classes_table"):
            return
        row = self.selected_class_table_index()
        if row is None:
            self.class_roster_table.setRowCount(0)
            return
        # Obtiene la clase de la fila seleccionada para pedirle al servidor sus estudiantes.
        c = self.classes[row]
        self.roster_heading.setText(f'Estudiantes vinculados · {c["name"]} · NRC {c["nrc"]}')
        try:
            students = self.api("GET", f'/classes/{c["nrc"]}/students')
        except ApiError as exc:
            QMessageBox.warning(self, "Error al consultar estudiantes", str(exc))
            return
        self.class_roster_table.setRowCount(len(students))
        for r, student in enumerate(students):
            self.class_roster_table.setItem(r, 0, QTableWidgetItem(student["full_name"]))
            self.class_roster_table.setItem(r, 1, QTableWidgetItem(student["email"]))
        self.populate_classes_table_counts(students, row)

    def populate_classes_table_counts(self, students, row):
        """Actualiza la tabla de clases con sus datos y cantidad de estudiantes."""
        # El endpoint /classes ya trae student_count; refrescar por coherencia tras altas.
        try:
            self.classes = self.api("GET", "/classes")
            self.populate_class_selectors()
            self.classes_table.blockSignals(True)
            self.classes_table.setRowCount(len(self.classes))
            for r, c in enumerate(self.classes):
                values = [c["nrc"], c["name"], str(c["start_time"])[:5], f'{c["tolerance_minutes"]} min', str(c["student_count"])]
                for col, value in enumerate(values):
                    self.classes_table.setItem(r, col, QTableWidgetItem(value))
            self.classes_table.selectRow(min(row, len(self.classes)-1) if self.classes else -1)
            self.classes_table.blockSignals(False)
        except ApiError:
            pass

    # ---------- Actions ----------
    def create_class(self):
        """Valida el formulario, crea una clase en el servidor y la selecciona."""
        name = self.new_class_name.text().strip()
        if len(name) < 2:
            QMessageBox.warning(self, "Nombre inválido", "Escribe un nombre para la clase.")
            return
        # Empaqueta el nombre, la hora y la tolerancia para enviarlos juntos al servidor.
        payload = {
            "name": name,
            "start_time": self.new_class_start.time().toString("HH:mm:ss"),
            "tolerance_minutes": self.new_class_tolerance.value(),
        }
        try:
            created = self.api("POST", "/classes", json=payload)
            self.new_class_name.clear()
            self.load_classes()
            # Selecciona la clase que acaba de crear el servidor.
            for i, c in enumerate(self.classes):
                if c["nrc"] == created["nrc"]:
                    self.current_class_index = i
                    break
            self.populate_class_selectors()
            self.load_dashboard_class()
            self.populate_classes_table()
            QMessageBox.information(
                self, "Clase creada",
                f'La clase «{created["name"]}» se guardó en MySQL con NRC {created["nrc"]}.\n'
                "Ahora puedes vincular estudiantes por correo institucional."
            )
        except ApiError as exc:
            QMessageBox.warning(self, "No se pudo crear la clase", str(exc))

    def enroll_student(self):
        """Vincula a la clase seleccionada un estudiante identificado por su correo."""
        row = self.selected_class_table_index()
        if row is None:
            QMessageBox.warning(self, "Selecciona una clase", "Selecciona una clase en la tabla antes de añadir estudiantes.")
            return
        c = self.classes[row]
        # Quita espacios y normaliza el correo a minúsculas antes de buscarlo.
        email = self.student_email_input.text().strip().lower()
        if not email:
            QMessageBox.warning(self, "Correo requerido", "Escribe el correo institucional del estudiante.")
            return
        try:
            result = self.api("POST", f'/classes/{c["nrc"]}/students', json={"email": email})
            self.student_email_input.clear()
            self.load_classes()
            QMessageBox.information(self, "Estudiante añadido", f'{result["student"]} fue vinculado a la clase NRC {c["nrc"]}.')
            # Mantiene seleccionada la misma clase en las dos pantallas.
            for i, item in enumerate(self.classes):
                if item["nrc"] == c["nrc"]:
                    self.current_class_index = i
                    break
            self.populate_class_selectors()
            self.populate_classes_table()
            self.refresh_roster_for_selected_class()
            self.load_dashboard_class()
        except ApiError as exc:
            QMessageBox.warning(self, "No se pudo añadir el estudiante", str(exc))

    def save_tolerance(self):
        """Guarda el margen de minutos permitido para llegar tarde."""
        c = self.current_class()
        if not c:
            QMessageBox.warning(self, "Sin clase", "Primero crea o selecciona una clase.")
            return
        try:
            updated = self.api(
                "PATCH",
                f'/classes/{c["nrc"]}/tolerance',
                params={"tolerance_minutes": self.tolerance.value()},
            )
            self.load_classes()
            QMessageBox.information(
                self, "Tolerancia guardada",
                f'La tolerancia de «{updated["name"]}» (NRC {updated["nrc"]}) ahora es '
                f'{updated["tolerance_minutes"]} minutos.'
            )
        except ApiError as exc:
            QMessageBox.warning(self, "No se pudo guardar la tolerancia", str(exc))

    def start_session(self):
        """Abre la asistencia de la clase actual e inicia el lector QR si está configurado."""
        if self.session_active:
            return
        c = self.current_class()
        if not c:
            QMessageBox.warning(self, "Sin clase", "Primero crea o selecciona una clase.")
            return
        try:
            # Comprueba que haya estudiantes antes de pedir al servidor que abra la sesión.
            self.roster = self.api("GET", f'/classes/{c["nrc"]}/students')
            if not self.roster:
                QMessageBox.warning(self, "Clase vacía", "Añade estudiantes desde Gestión de clases antes de iniciar.")
                return
            session = self.api("POST", f'/classes/{c["nrc"]}/sessions/start')
            self.current_session_id = session["id"]
            self.session_active = True
            self.session_label.setText(f'● ASISTENCIA EN CURSO · SESIÓN {session["id"]} · NRC {c["nrc"]}')
            self.session_label.setStyleSheet("color:#18794E;font-weight:800;")
            self.start_btn.setText("●  Asistencia en curso")
            self.start_btn.setObjectName("Running")
            self.start_btn.setStyleSheet("background:#18794E;color:white;border:none;border-radius:8px;padding:10px 13px;font-weight:800;")
            self.start_btn.setEnabled(False)
            self.finish_btn.setEnabled(True)
            self.course_combo.setEnabled(False)
            self.tolerance.setEnabled(False)
            self.save_config_btn.setEnabled(False)
            self.load_roster_and_records()
            self.refresh_history()
            station_started = self.start_station(show_errors=False)
            QMessageBox.information(
                self, "Asistencia iniciada",
                f'Se creó la sesión {session["id"]} en MySQL para la clase NRC {c["nrc"]}.\n'
                + ("La estación ESP32-CAM comenzó a leer los QR."
                   if station_started else
                   "Escriba la dirección de la ESP32-CAM en el panel de la estación para leer QR.")
            )
        except ApiError as exc:
            QMessageBox.warning(self, "No se pudo iniciar asistencia", str(exc))

    def finish_session(self):
        """Cierra la sesión y pide al servidor marcar ausentes a quienes no registraron."""
        if not self.session_active or self.current_session_id is None:
            return
        # Pide confirmación para evitar cerrar la clase por un clic accidental.
        answer = QMessageBox.question(
            self, "Finalizar clase", "¿Deseas finalizar la sesión y marcar ausentes a quienes no registraron?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if answer != QMessageBox.Yes:
            return
        try:
            finished = self.api("POST", f"/sessions/{self.current_session_id}/finish")
            self.stop_station()
            self.session_active = False
            self.session_label.setText(f'● Sesión finalizada · ID {finished["id"]}')
            self.session_label.setStyleSheet("color:#B42318;font-weight:800;")
            self.set_device_status("Sesión cerrada", False)
            self.start_btn.setText("▶  Iniciar asistencia")
            self.start_btn.setObjectName("Success")
            self.start_btn.setStyleSheet("")
            self.start_btn.setEnabled(True)
            self.finish_btn.setEnabled(False)
            self.course_combo.setEnabled(True)
            self.tolerance.setEnabled(True)
            self.save_config_btn.setEnabled(True)
            self.load_roster_and_records()
            self.refresh_history()
            QMessageBox.information(
                self, "Clase finalizada",
                "La sesión se cerró en MySQL. Los estudiantes sin registro quedaron marcados como ausentes."
            )
        except ApiError as exc:
            QMessageBox.warning(self, "No se pudo finalizar la clase", str(exc))

    def manual_attendance(self):
        """Registra manualmente al estudiante seleccionado durante una sesión abierta."""
        if self.current_session_id is None or not self.session_active:
            QMessageBox.warning(self, "No hay sesión activa", "Primero pulsa «Iniciar asistencia».")
            return
        # Averigua qué fila está seleccionada para identificar al estudiante elegido.
        row = self.attendance_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Selecciona un estudiante", "Selecciona un estudiante de la tabla.")
            return
        email_item = self.attendance_table.item(row, 1)
        email = email_item.text() if email_item else ""
        try:
            result = self.api(
                "POST",
                f"/sessions/{self.current_session_id}/attendance/manual",
                json={"email": email},
            )
            self.load_roster_and_records()
            QMessageBox.information(
                self, "Asistencia añadida",
                f'{result["student_name"]} quedó registrado manualmente en MySQL.'
            )
        except ApiError as exc:
            QMessageBox.warning(self, "No se pudo añadir la asistencia", str(exc))

    def render_attendance_table(self, *_):
        """Combina estudiantes y asistencias para mostrar estados, horas y totales."""
        if not hasattr(self, "attendance_table"):
            return
        # Crea una búsqueda rápida: dado un correo, permite encontrar su registro de asistencia.
        record_by_email = {r["student_email"].lower(): r for r in self.records}
        rows = []
        for student in self.roster:
            email = student["email"]
            record = record_by_email.get(email.lower())
            if record:
                status_map = {
                    "present": "Presente",
                    "manual": "Manual",
                    "tardy": "Tarde",
                    "absent": "Ausente",
                }
                state = status_map.get(record["status"], record["status"])
                time_value = record["registered_at"]
                if time_value:
                    time_value = time_value.replace("T", " ")[:16]
                    time_value = time_value[-5:]
                else:
                    time_value = "—"
            else:
                state = "Pendiente"
                time_value = "—"
            rows.append({
                "name": student["full_name"],
                "email": email,
                "time": time_value,
                "status": state,
            })

        term = self.search_attendance.text().lower().strip() if hasattr(self, "search_attendance") else ""
        # Conserva solo las filas cuyo nombre o correo contiene el texto escrito en la búsqueda.
        shown = [r for r in rows if term in r["name"].lower() or term in r["email"].lower()]
        colors = {
            "Presente": ("#DDF7E8", "#18794E"),
            "Manual": ("#DDF7E8", "#18794E"),
            "Tarde": ("#FCE8E7", "#B42318"),
            "Ausente": ("#FCE8E7", "#B42318"),
            "Pendiente": ("#EDF0F5", "#596579"),
        }
        self.attendance_table.setRowCount(len(shown))
        for r, student in enumerate(shown):
            bg, fg = colors.get(student["status"], ("#EDF0F5", "#596579"))
            for col, value in enumerate([student["name"], student["email"], student["time"], student["status"]]):
                item = QTableWidgetItem(value)
                item.setBackground(QColor(bg))
                if col == 3:
                    item.setForeground(QColor(fg))
                    item.setFont(QFont("Segoe UI", 9, QFont.Bold))
                self.attendance_table.setItem(r, col, item)

        # Cuenta los estados de toda la clase para actualizar los indicadores numéricos.
        present = sum(r["status"] in ("Presente", "Manual") for r in rows)
        late_absent = sum(r["status"] in ("Tarde", "Ausente") for r in rows)
        pending = sum(r["status"] == "Pendiente" for r in rows)
        self.metric_total.value_label.setText(str(len(rows)))
        self.metric_present.value_label.setText(str(present))
        self.metric_late.value_label.setText(str(late_absent))
        self.metric_pending.value_label.setText(str(pending))

    def refresh_history(self):
        """Consulta las sesiones al backend y actualiza la tabla de historial."""
        if not hasattr(self, "history_table"):
            return
        # Solicita las sesiones al servidor y coloca cada sesión en una fila de la tabla.
        try:
            sessions = self.api("GET", "/sessions")
        except ApiError as exc:
            # At construction time don't spam a dialog if server hasn't started.
            if self.isVisible():
                QMessageBox.warning(self, "No se pudo cargar historial", str(exc))
            return
        self.history_table.setRowCount(len(sessions))
        for r, session in enumerate(sessions):
            values = [
                str(session["id"]),
                session["nrc"],
                str(session["started_at"]).replace("T", " ")[:19],
                str(session["finished_at"]).replace("T", " ")[:19] if session["finished_at"] else "—",
                "Activa" if session["status"] == "active" else "Finalizada",
            ]
            for col, value in enumerate(values):
                self.history_table.setItem(r, col, QTableWidgetItem(value))

    def export_attendance(self):
        """Exporta a CSV la lista de estudiantes y su estado de asistencia."""
        if not self.roster:
            QMessageBox.information(self, "Sin estudiantes", "No hay estudiantes para exportar en esta clase.")
            return
        # Abre el selector de archivos para elegir el nombre y la ubicación del CSV.
        path, _ = QFileDialog.getSaveFileName(self, "Exportar asistencia", "asistencia.csv", "CSV (*.csv)")
        if not path:
            return
        record_by_email = {r["student_email"].lower(): r for r in self.records}
        c = self.current_class()
        try:
            # Abre el archivo para escribirlo; esta codificación conserva acentos al usar Excel.
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                # Crea una herramienta que separa los datos en columnas dentro del archivo CSV.
                writer = csv.writer(f)
                writer.writerow(["NRC", "Asignatura", "Nombre", "Correo institucional", "Hora de registro", "Estado", "Origen"])
                status_map = {"present": "Presente", "manual": "Manual", "tardy": "Tarde", "absent": "Ausente"}
                for student in self.roster:
                    record = record_by_email.get(student["email"].lower())
                    if record:
                        registered = record["registered_at"] or "—"
                        state = status_map.get(record["status"], record["status"])
                        source = record["source"]
                    else:
                        registered, state, source = "—", "Pendiente", "—"
                    writer.writerow([c["nrc"], c["name"], student["full_name"], student["email"], registered, state, source])
            QMessageBox.information(self, "Exportación completada", f"Se guardó el CSV en:\n{path}")
        except OSError as exc:
            QMessageBox.critical(self, "Error al exportar", str(exc))


# Punto de entrada: solo se ejecuta cuando este archivo se inicia directamente.
if __name__ == "__main__":
    # Este bloque solo se ejecuta cuando se abre este archivo directamente.
    # QApplication crea la aplicación gráfica y organiza los clics y demás eventos.
    app = QApplication(sys.argv)
    app.setFont(QFont("Segoe UI", 10))
    window = AulaCheckApp()
    window.show()
    sys.exit(app.exec())
