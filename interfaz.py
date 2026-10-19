import sys
import csv
import os
from datetime import datetime
import requests

from PySide6.QtCore import Qt, QTime, QTimer
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QFrame, QTableWidget, QTableWidgetItem, QHeaderView,
    QLineEdit, QComboBox, QSpinBox, QTimeEdit, QMessageBox, QAbstractItemView,
    QFileDialog, QStackedWidget, QDialog, QFormLayout, QTabWidget, QCheckBox,
    QDialogButtonBox, QInputDialog, QMenu
)

API_BASE = os.getenv("AULACHECK_API_URL", "http://127.0.0.1:8000").rstrip("/")


class ApiError(Exception):
    pass


class AulaCheckApp(QMainWindow):
    """Interfaz PySide6 conectada al backend FastAPI de AulaCheck."""

    def __init__(self, token, user):
        super().__init__()
        self.token = token
        self.user = user
        self.role = user["role"]
        self.setWindowTitle("AulaCheck | Sistema de asistencia académica")
        self.resize(1580, 900)
        self.setMinimumSize(1120, 680)

        self.classes = []
        self.current_class_index = 0
        self.current_session_id = None
        self.session_active = False
        self.roster = []
        self.records = []

        # Estilos globales: colores, tipografía, botones, campos y tablas.
        self.setStyleSheet("""
            QMainWindow, QWidget { background:#F3F6FC; color:#17365D; font-family:'Segoe UI'; font-size:13px; }
            QLabel { background:transparent; }
            QFrame#Sidebar { background:#10233F; border-radius:0px; }
            QLabel#Brand { color:white; font-size:24px; font-weight:800; }
            QLabel#SideCaption { color:#9FAFC6; font-size:10px; font-weight:800; }
            QPushButton#Nav { text-align:left; color:#E0E9F6; background:transparent; border:none;
                padding:13px 14px; border-radius:9px; font-size:13px; }
            QPushButton#Nav:hover, QPushButton#Nav:checked { background:#1458CB; color:white; }
            QLabel#PageTitle { font-size:29px; font-weight:800; color:#122E56; }
            QLabel#Muted { color:#61799D; font-size:13px; }
            QFrame#Card, QFrame#Panel { background:white; border:1px solid #DCE7F7; border-radius:13px; }
            QLabel#MetricTitle { color:#536E99; font-size:12px; }
            QLabel#MetricValue { color:#102A4E; font-size:28px; font-weight:800; }
            QPushButton#Primary { background:#145FE5; color:white; border:none; border-radius:8px;
                padding:10px 14px; font-weight:700; }
            QPushButton#Primary:hover { background:#104FC2; }
            QPushButton#Secondary { background:#F1F5FC; color:#245FE0; border:1px solid #D8E4F5; border-radius:8px;
                padding:9px 12px; font-weight:700; }
            QPushButton#Danger { background:#FFF0EF; color:#B42318; border:1px solid #FFD1CD; border-radius:8px;
                padding:10px 13px; font-weight:700; }
            QPushButton#Success { background:#30B889; color:white; border:none; border-radius:8px;
                padding:10px 13px; font-weight:700; }
            QPushButton#Running { background:#18794E; color:white; border:none; border-radius:8px;
                padding:10px 13px; font-weight:800; }
            QLineEdit, QComboBox, QSpinBox, QTimeEdit {
                background:white; border:1px solid #D5E1F1; border-radius:7px; padding:8px 10px; min-height:20px;
            }
            QTableWidget { background:white; alternate-background-color:#F8FAFE; border:1px solid #DFE8F5; gridline-color:#E8EEF7;
                selection-background-color:#EAF1FF; selection-color:#17365D; }
            QHeaderView::section { background:#F4F7FC; color:#536B91; border:0; border-bottom:1px solid #DFE8F5;
                padding:12px 10px; font-weight:700; }
            QCheckBox { spacing:8px; }
            QMenu { background:white; border:1px solid #DCE7F7; padding:5px; }
            QMenu::item { padding:8px 24px; }
            QMenu::item:selected { background:#EEF4FF; color:#245FE0; }
        """)

        # Contenedor raíz: organiza la barra lateral y el área principal.
        root = QWidget()
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(18, 18, 18, 18)
        root_layout.setSpacing(18)

        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(258)
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(18, 22, 18, 18)
        side.setSpacing(9)
        brand = QLabel("✓   AulaCheck")
        brand.setObjectName("Brand")
        side.addWidget(brand)
        tagline = QLabel("ASISTENCIA ACADÉMICA")
        tagline.setObjectName("SideCaption")
        side.addWidget(tagline)
        side.addSpacing(28)
        side.addWidget(self.section_label("MENÚ PRINCIPAL"))

        # Botones de navegación para cambiar entre panel, clases, historial y acerca de.
        self.nav_buttons = []
        for text, index in [
            ("Panel de asistencia", 0),
            ("Gestión de clases", 1),
            ("Historial", 2),
            ("Acerca de", 3),
        ]:
            btn = QPushButton(text)
            btn.setObjectName("Nav")
            btn.setCheckable(True)
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
        self.device_status.setWordWrap(True)
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
        self.stack = QStackedWidget()
        self.stack.addWidget(self.build_dashboard())
        self.stack.addWidget(self.build_classes_page())
        self.stack.addWidget(self.build_history_page())
        self.stack.addWidget(self.build_about_page())
        main_layout.addWidget(self.stack)
        root_layout.addWidget(sidebar)
        root_layout.addWidget(main_area, 1)
        self.setCentralWidget(root)

        # Carga inicial: rellena la interfaz con los datos actuales del backend.
        self.load_classes(show_errors=False)
        self.refresh_history()

        # Actualización automática cada 30 segundos.
        # QTimer ejecuta el método dentro del ciclo de eventos de Qt, sin bloquear la ventana.
        self.refresh_timer = QTimer(self)
        self.refresh_timer.setInterval(30_000)  # 30.000 milisegundos = 30 segundos.
        self.refresh_timer.timeout.connect(self.refresh_automatically)
        self.refresh_timer.start()

    # ---------- API helpers: comunicación HTTP con el backend FastAPI ----------
    def api(self, method, path, **kwargs):
        """Realiza una petición HTTP y convierte errores de red/API en ApiError."""
        try:
            headers = dict(kwargs.pop("headers", {}))
            headers["Authorization"] = f"Bearer {self.token}"
            response = requests.request(method, f"{API_BASE}{path}", timeout=10, headers=headers, **kwargs)
        except requests.RequestException as exc:
            raise ApiError(
                "No se pudo conectar con FastAPI.\n"
                "Comprueba que el backend esté ejecutándose en http://127.0.0.1:8000.\n\n"
                f"Detalle: {exc}"
            )
        if not response.ok:
            try:
                detail = response.json().get("detail", response.text)
            except ValueError:
                detail = response.text
            raise ApiError(f"Error HTTP {response.status_code}: {detail}")
        if response.status_code == 204 or not response.content:
            return None
        return response.json()

    def run_action(self, action, success_message=None):
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

    def logout(self):
        self.token = ""
        self.close()

    def current_class(self):
        if not self.classes:
            return None
        self.current_class_index = max(0, min(self.current_class_index, len(self.classes) - 1))
        return self.classes[self.current_class_index]

    def current_nrc(self):
        c = self.current_class()
        return c["nrc"] if c else None

    # ---------- UI helpers ----------
    def section_label(self, text):
        l = QLabel(text)
        l.setStyleSheet("font-size:11px;font-weight:800;color:#6B778C;letter-spacing:1px;")
        return l

    def field_label(self, text):
        label = QLabel(text)
        label.setStyleSheet("color:#36557F;font-weight:600;")
        return label

    def panel(self):
        f = QFrame()
        f.setObjectName("Panel")
        return f

    def page_header(self, title, subtitle):
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

    def metric_card(self, title, value, icon="•", accent="#3275EA", tint="#EFF4FF"):
        card = QFrame()
        card.setObjectName("Card")
        lay = QHBoxLayout(card)
        lay.setContentsMargins(17, 13, 17, 13)
        lay.setSpacing(14)
        icon_badge = QLabel(icon)
        icon_badge.setAlignment(Qt.AlignCenter)
        icon_badge.setFixedSize(48, 48)
        icon_badge.setStyleSheet(f"color:{accent};background:{tint};border-radius:24px;font-size:21px;font-weight:800;")
        lay.addWidget(icon_badge)
        text_col = QVBoxLayout()
        text_col.setSpacing(2)
        t = QLabel(title)
        t.setObjectName("MetricTitle")
        v = QLabel(str(value))
        v.setObjectName("MetricValue")
        text_col.addWidget(t)
        text_col.addWidget(v)
        lay.addLayout(text_col)
        lay.addStretch()
        card.value_label = v
        return card

    def setup_table(self, table):
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
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(15)

        top = QHBoxLayout()
        top.setContentsMargins(8, 4, 8, 4)
        title_col = QVBoxLayout()
        title = QLabel("Panel de asistencia")
        title.setObjectName("PageTitle")
        subtitle = QLabel("Consulta y registra la asistencia de tus estudiantes en tiempo real.")
        subtitle.setObjectName("Muted")
        title_col.addWidget(title)
        title_col.addWidget(subtitle)
        top.addLayout(title_col)
        top.addStretch()
        date_box = QFrame()
        date_box.setObjectName("Card")
        date_row = QHBoxLayout(date_box)
        date_row.setContentsMargins(13, 7, 13, 7)
        month_names = ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre")
        today = datetime.now()
        date_label = QLabel(f"Fecha · {today.day} de {month_names[today.month - 1]} de {today.year}")
        date_label.setStyleSheet("color:#385B91;font-weight:700;")
        date_row.addWidget(date_label)
        top.addWidget(date_box)
        account = QLabel(f"{self.user['email']}\n{'Administrador' if self.role == 'admin' else 'Profesor'}")
        account.setStyleSheet("color:#24466F;font-weight:700;padding:4px 12px;")
        top.addWidget(account)
        logout = QPushButton("Cerrar sesión")
        logout.setObjectName("Secondary")
        logout.clicked.connect(self.logout)
        top.addWidget(logout)
        layout.addLayout(top)

        config = self.panel()
        cg = QGridLayout(config)
        cg.setContentsMargins(18, 15, 18, 16)
        cg.setHorizontalSpacing(16)
        cg.setVerticalSpacing(9)
        class_heading = QLabel("Información de la clase")
        class_heading.setStyleSheet("font-size:17px;font-weight:800;color:#17365D;")
        cg.addWidget(class_heading, 0, 0, 1, 5)
        self.course_combo = QComboBox()
        self.course_combo.currentIndexChanged.connect(self.on_dashboard_class_changed)
        self.start_time_label = QLabel("—")
        self.start_time_label.setStyleSheet("font-size:14px;font-weight:700;color:#17365D;background:#F5F8FD;border:1px solid #D5E1F1;border-radius:7px;padding:10px 12px;")
        self.start_time_label.setMinimumHeight(22)
        self.tolerance = QSpinBox()
        self.tolerance.setRange(0, 180)
        self.tolerance.setSuffix(" min")
        cg.addWidget(self.field_label("Asignatura / NRC"), 1, 0)
        cg.addWidget(self.field_label("Hora de inicio (solo lectura)"), 1, 2)
        cg.addWidget(self.field_label("Tolerancia ajustable"), 1, 3)
        cg.addWidget(self.course_combo, 2, 0, 1, 2)
        cg.addWidget(self.start_time_label, 2, 2)
        cg.addWidget(self.tolerance, 2, 3)
        self.save_config_btn = QPushButton("Guardar tolerancia")
        self.save_config_btn.setObjectName("Primary")
        self.save_config_btn.clicked.connect(self.save_tolerance)
        cg.addWidget(self.save_config_btn, 2, 4)
        cg.setColumnStretch(0, 4)
        cg.setColumnStretch(1, 1)
        cg.setColumnStretch(2, 3)
        cg.setColumnStretch(3, 3)
        cg.setColumnStretch(4, 2)
        layout.addWidget(config)

        cards = QHBoxLayout()
        cards.setSpacing(14)
        self.metric_total = self.metric_card("Estudiantes de la clase", 0, "01", "#3275EA", "#EFF4FF")
        self.metric_present = self.metric_card("Asistencia válida", 0, "✓", "#0E9C72", "#EAF8F3")
        self.metric_late = self.metric_card("Tarde / ausente", 0, "!", "#F19300", "#FFF6E8")
        self.metric_pending = self.metric_card("Pendientes", 0, "…", "#8058E8", "#F4F0FF")
        for c in [self.metric_total, self.metric_present, self.metric_late, self.metric_pending]:
            cards.addWidget(c)
        layout.addLayout(cards)

        table_panel = self.panel()
        tp = QVBoxLayout(table_panel)
        tp.setContentsMargins(17, 15, 17, 15)
        header = QHBoxLayout()
        list_heading = QLabel("Lista de asistencia")
        list_heading.setStyleSheet("font-size:17px;font-weight:800;color:#17365D;")
        header.addWidget(list_heading)
        header.addStretch()
        self.search_attendance = QLineEdit()
        self.search_attendance.setPlaceholderText("Buscar estudiante...")
        self.search_attendance.setMaximumWidth(300)
        self.search_attendance.textChanged.connect(self.render_attendance_table)
        header.addWidget(self.search_attendance)
        self.attendance_filter = "Todos"
        self.attendance_filter_button = QPushButton("▽  Filtros")
        self.attendance_filter_button.setObjectName("Secondary")
        self.attendance_filter_button.clicked.connect(self.show_attendance_filter)
        header.addWidget(self.attendance_filter_button)
        tp.addLayout(header)

        self.attendance_table = QTableWidget(0, 7)
        self.attendance_table.setHorizontalHeaderLabels(["", "#", "Nombre del estudiante", "Correo institucional", "Hora de registro", "Estado", ""])
        self.attendance_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)
        self.attendance_table.setColumnWidth(0, 48)
        self.attendance_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.attendance_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.attendance_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.attendance_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.attendance_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)
        self.attendance_table.horizontalHeader().setSectionResizeMode(6, QHeaderView.Fixed)
        self.attendance_table.setColumnWidth(6, 48)
        self.setup_table(self.attendance_table)
        self.attendance_table.verticalHeader().setDefaultSectionSize(48)
        self.attendance_table.setAlternatingRowColors(True)
        tp.addWidget(self.attendance_table, 1)
        layout.addWidget(table_panel, 1)

        action_panel = self.panel()
        action_layout = QHBoxLayout(action_panel)
        action_layout.setContentsMargins(14, 11, 14, 11)
        action_layout.setSpacing(10)
        self.session_label = QLabel("● Sesión no iniciada")
        self.session_label.setStyleSheet("color:#536E99;background:#F1F5FC;border-radius:7px;padding:9px;font-weight:700;")
        action_layout.addWidget(self.session_label, 1)
        self.start_btn = QPushButton("Iniciar asistencia")
        self.start_btn.setObjectName("Success")
        self.start_btn.clicked.connect(self.start_session)
        self.finish_btn = QPushButton("Finalizar clase")
        self.finish_btn.setObjectName("Danger")
        self.finish_btn.clicked.connect(self.finish_session)
        self.finish_btn.setEnabled(False)
        self.manual_btn = QPushButton("Añadir asistencia")
        self.manual_btn.setObjectName("Secondary")
        self.manual_btn.clicked.connect(self.manual_attendance)
        self.export_btn = QPushButton("Guardar / exportar")
        self.export_btn.setObjectName("Primary")
        self.export_btn.clicked.connect(self.export_attendance)
        self.refresh_btn = QPushButton("Actualizar")
        self.refresh_btn.setObjectName("Secondary")
        self.refresh_btn.clicked.connect(self.refresh_dashboard_data)
        for b in [self.start_btn, self.finish_btn, self.manual_btn, self.export_btn, self.refresh_btn]:
            b.setMinimumHeight(42)
            action_layout.addWidget(b)
        layout.addWidget(action_panel)
        return page

    def build_classes_page(self):
        """Construye la pantalla para gestionar clases asignadas y estudiantes."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)
        layout.addLayout(self.page_header("Mis clases", "Clases asignadas por el administrador. Vincula estudiantes registrados por correo institucional."))

        classes_panel = self.panel()
        cl = QVBoxLayout(classes_panel)
        cl.setContentsMargins(16, 14, 16, 14)
        cl.addWidget(self.section_label("MIS CLASES — SELECCIONA UNA PARA ADMINISTRAR SU LISTA"))
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
        """Construye la tabla con el historial de sesiones de asistencia."""
        page = QWidget()
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
        """Construye la pantalla informativa del proyecto y sus integrantes."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)
        layout.addLayout(self.page_header("Acerca del proyecto", "Quiénes somos, qué hacemos y qué valor aportamos."))
        panel = self.panel()
        pl = QVBoxLayout(panel)
        pl.setContentsMargins(26, 24, 26, 24)
        pl.setSpacing(12)
        title = QLabel("AulaCheck · Asistencia académica mediante QR dinámicos")
        title.setStyleSheet("font-size:20px;font-weight:800;color:#17365D;")
        pl.addWidget(title)
        desc = QLabel(
            "Somos un equipo de estudiantes que integra programación, interfaces y electrónica para facilitar "
            "el registro de asistencia. La propuesta combina Flutter para mostrar el QR dinámico, ESP32-CAM "
            "para capturarlo, FastAPI para validar la solicitud, MySQL para almacenar los datos y PySide6 "
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

    # ---------- Carga y sincronización de datos desde FastAPI ----------
    def load_classes(self, show_errors=True):
        """Carga clases y sincroniza selectores, panel principal e historial."""
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
        self.course_combo.blockSignals(True)
        self.course_combo.clear()
        for c in self.classes:
            self.course_combo.addItem(f'{c["name"]} · NRC {c["nrc"]}')
        if self.classes:
            self.course_combo.setCurrentIndex(self.current_class_index)
        self.course_combo.blockSignals(False)

    def populate_classes_table(self):
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
                    self.start_btn.setText("Asistencia en curso")
                    self.start_btn.setObjectName("Running")
                    self.start_btn.setEnabled(False)
                    self.finish_btn.setEnabled(True)

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
        self.current_class_index = index
        self.current_session_id = None
        self.session_label.setText("● Sesión no iniciada")
        self.session_label.setStyleSheet("color:#6B778C;font-weight:700;")
        self.start_btn.setText("Iniciar asistencia")
        self.start_btn.setObjectName("Success")
        self.start_btn.setStyleSheet("")
        self.start_btn.setEnabled(True)
        self.finish_btn.setEnabled(False)
        self.load_dashboard_class()
        self.populate_classes_table()
        self.refresh_roster_for_selected_class()

    def selected_class_table_index(self):
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
        name = self.new_class_name.text().strip()
        if len(name) < 2:
            QMessageBox.warning(self, "Nombre inválido", "Escribe un nombre para la clase.")
            return
        payload = {
            "name": name,
            "start_time": self.new_class_start.time().toString("HH:mm:ss"),
            "tolerance_minutes": self.new_class_tolerance.value(),
        }
        try:
            created = self.api("POST", "/classes", json=payload)
            self.new_class_name.clear()
            self.load_classes()
            # Select the class that was just created.
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
        row = self.selected_class_table_index()
        if row is None:
            QMessageBox.warning(self, "Selecciona una clase", "Selecciona una clase en la tabla antes de añadir estudiantes.")
            return
        c = self.classes[row]
        email = self.student_email_input.text().strip().lower()
        if not email:
            QMessageBox.warning(self, "Correo requerido", "Escribe el correo institucional del estudiante.")
            return
        try:
            result = self.api("POST", f'/classes/{c["nrc"]}/students', json={"email": email})
            self.student_email_input.clear()
            self.load_classes()
            QMessageBox.information(self, "Estudiante añadido", f'{result["student"]} fue vinculado a la clase NRC {c["nrc"]}.')
            # Keep the selected class in both screens.
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
        if self.session_active:
            return
        c = self.current_class()
        if not c:
            QMessageBox.warning(self, "Sin clase", "Primero crea o selecciona una clase.")
            return
        try:
            self.roster = self.api("GET", f'/classes/{c["nrc"]}/students')
            if not self.roster:
                QMessageBox.warning(self, "Clase vacía", "Añade estudiantes desde Gestión de clases antes de iniciar.")
                return
            session = self.api("POST", f'/classes/{c["nrc"]}/sessions/start')
            self.current_session_id = session["id"]
            self.session_active = True
            self.session_label.setText(f'● ASISTENCIA EN CURSO · SESIÓN {session["id"]} · NRC {c["nrc"]}')
            self.session_label.setStyleSheet("color:#18794E;font-weight:800;")
            self.start_btn.setText("Asistencia en curso")
            self.start_btn.setObjectName("Running")
            self.start_btn.setStyleSheet("background:#18794E;color:white;border:none;border-radius:8px;padding:10px 13px;font-weight:800;")
            self.start_btn.setEnabled(False)
            self.finish_btn.setEnabled(True)
            self.course_combo.setEnabled(False)
            self.tolerance.setEnabled(False)
            self.save_config_btn.setEnabled(False)
            self.device_status.setText("●  Backend activo · ESP32-CAM pendiente")
            self.device_status.setStyleSheet("color:#8DE0B0;font-size:12px;font-weight:700;")
            self.load_roster_and_records()
            self.refresh_history()
            QMessageBox.information(
                self, "Asistencia iniciada",
                f'Se creó la sesión {session["id"]} en MySQL para la clase NRC {c["nrc"]}.\n'
                "La conexión física con el ESP32-CAM todavía no está implementada."
            )
        except ApiError as exc:
            QMessageBox.warning(self, "No se pudo iniciar asistencia", str(exc))

    def finish_session(self):
        if not self.session_active or self.current_session_id is None:
            return
        answer = QMessageBox.question(
            self, "Finalizar clase", "¿Deseas finalizar la sesión y marcar ausentes a quienes no registraron?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if answer != QMessageBox.Yes:
            return
        try:
            finished = self.api("POST", f"/sessions/{self.current_session_id}/finish")
            self.session_active = False
            self.session_label.setText(f'● Sesión finalizada · ID {finished["id"]}')
            self.session_label.setStyleSheet("color:#B42318;font-weight:800;")
            self.device_status.setText("●  Sesión cerrada · ESP32-CAM pendiente")
            self.device_status.setStyleSheet("color:#F6D98B;font-size:12px;font-weight:700;")
            self.start_btn.setText("Iniciar asistencia")
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
        if self.current_session_id is None or not self.session_active:
            QMessageBox.warning(self, "No hay sesión activa", "Primero pulsa «Iniciar asistencia».")
            return
        row = self.attendance_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Selecciona un estudiante", "Selecciona un estudiante de la tabla.")
            return
        self.manual_attendance_for_table_row(row)

    def manual_attendance_for_table_row(self, row):
        if self.current_session_id is None or not self.session_active:
            QMessageBox.warning(self, "No hay sesión activa", "Primero pulsa «Iniciar asistencia».")
            return
        email_item = self.attendance_table.item(row, 3)
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
        if not hasattr(self, "attendance_table"):
            return
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

        term = self.search_attendance.text().casefold().strip() if hasattr(self, "search_attendance") else ""
        state_filter = getattr(self, "attendance_filter", "Todos")
        shown = [
            (index, student) for index, student in enumerate(rows, start=1)
            if (term in student["name"].casefold() or term in student["email"].casefold())
            and (state_filter == "Todos" or student["status"] == state_filter)
        ]
        colors = {
            "Presente": ("#DDF7E8", "#18794E"),
            "Manual": ("#DDF7E8", "#18794E"),
            "Tarde": ("#FFF2CF", "#AF6500"),
            "Ausente": ("#FCE8E7", "#B42318"),
            "Pendiente": ("#EDF0F5", "#596579"),
        }
        self.attendance_table.setRowCount(len(shown))
        for r, (number, student) in enumerate(shown):
            bg, fg = colors.get(student["status"], ("#EDF0F5", "#596579"))
            checkbox = QTableWidgetItem()
            checkbox.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsUserCheckable)
            checkbox.setCheckState(Qt.Unchecked)
            checkbox.setTextAlignment(Qt.AlignCenter)
            self.attendance_table.setItem(r, 0, checkbox)
            self.attendance_table.setItem(r, 1, QTableWidgetItem(str(number)))
            for col, value in enumerate([student["name"], student["email"], student["time"], student["status"]], start=2):
                item = QTableWidgetItem(value)
                if col == 5:
                    item.setBackground(QColor(bg))
                    item.setForeground(QColor(fg))
                    item.setFont(QFont("Segoe UI", 9, QFont.Bold))
                self.attendance_table.setItem(r, col, item)
            action = QPushButton("···")
            action.setObjectName("Secondary")
            action.setMaximumWidth(38)
            action.clicked.connect(lambda checked=False, row=r, button=action: self.show_student_actions(row, button))
            self.attendance_table.setCellWidget(r, 6, action)

        present = sum(r["status"] in ("Presente", "Manual") for r in rows)
        late_absent = sum(r["status"] in ("Tarde", "Ausente") for r in rows)
        pending = sum(r["status"] == "Pendiente" for r in rows)
        self.metric_total.value_label.setText(str(len(rows)))
        self.metric_present.value_label.setText(str(present))
        self.metric_late.value_label.setText(str(late_absent))
        self.metric_pending.value_label.setText(str(pending))

    def show_attendance_filter(self):
        menu = QMenu(self)
        for label in ("Todos", "Presente", "Manual", "Tarde", "Ausente", "Pendiente"):
            action = menu.addAction(label)
            action.triggered.connect(lambda checked=False, value=label: self.set_attendance_filter(value))
        menu.exec(self.attendance_filter_button.mapToGlobal(self.attendance_filter_button.rect().bottomLeft()))

    def set_attendance_filter(self, value):
        self.attendance_filter = value
        label = "Filtros" if value == "Todos" else value
        self.attendance_filter_button.setText(f"▽  {label}")
        self.render_attendance_table()

    def show_student_actions(self, row, button):
        self.attendance_table.setCurrentCell(row, 2)
        menu = QMenu(self)
        manual = menu.addAction("Registrar asistencia manual")
        manual.triggered.connect(lambda: self.manual_attendance_for_table_row(row))
        menu.exec(button.mapToGlobal(button.rect().bottomLeft()))

    def refresh_history(self):
        """Consulta las sesiones al backend y actualiza la tabla de historial."""
        if not hasattr(self, "history_table"):
            return
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
        path, _ = QFileDialog.getSaveFileName(self, "Exportar asistencia", "asistencia.csv", "CSV (*.csv)")
        if not path:
            return
        record_by_email = {r["student_email"].lower(): r for r in self.records}
        c = self.current_class()
        try:
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
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


def request_api(token, method, path, **kwargs):
    headers = dict(kwargs.pop("headers", {}))
    headers["Authorization"] = f"Bearer {token}"
    try:
        response = requests.request(method, f"{API_BASE}{path}", headers=headers, timeout=10, **kwargs)
    except requests.RequestException as exc:
        raise ApiError(f"No se pudo conectar con {API_BASE}. Comprueba que FastAPI esté activo.\n\n{exc}")
    if not response.ok:
        try:
            detail = response.json().get("detail", response.text)
        except ValueError:
            detail = response.text
        raise ApiError(f"Error HTTP {response.status_code}: {detail}")
    return response.json() if response.content else None


class LoginDialog(QDialog):
    """Pantalla de acceso con pestañas independientes para administrador y profesor."""
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AulaCheck · Iniciar sesión")
        self.setMinimumWidth(430)
        self.auth = None
        layout = QVBoxLayout(self)
        title = QLabel("◈ AulaCheck")
        title.setStyleSheet("font-size:25px;font-weight:800;color:#17365D;padding:8px;")
        layout.addWidget(title, alignment=Qt.AlignCenter)
        layout.addWidget(QLabel("Selecciona tu tipo de cuenta e inicia sesión."), alignment=Qt.AlignCenter)
        self.tabs = QTabWidget()
        self.fields = {}
        for role, label in (("admin", "Administrador"), ("professor", "Profesor")):
            pane = QWidget()
            form = QFormLayout(pane)
            email = QLineEdit()
            email.setPlaceholderText("admin" if role == "admin" else "correo@institucion.edu")
            password = QLineEdit()
            password.setEchoMode(QLineEdit.Password)
            password.setPlaceholderText("Contraseña")
            password.returnPressed.connect(lambda r=role: self.sign_in(r))
            form.addRow("Usuario" if role == "admin" else "Correo", email)
            form.addRow("Contraseña", password)
            self.tabs.addTab(pane, label)
            self.fields[role] = (email, password)
        layout.addWidget(self.tabs)
        btn = QPushButton("Iniciar sesión")
        btn.setObjectName("Primary")
        btn.clicked.connect(lambda: self.sign_in("admin" if self.tabs.currentIndex() == 0 else "professor"))
        layout.addWidget(btn)

    def sign_in(self, selected_role):
        email, password = self.fields[selected_role]
        try:
            response = requests.post(f"{API_BASE}/auth/login", json={
                "email": email.text().strip(), "password": password.text()
            }, timeout=10)
        except requests.RequestException as exc:
            QMessageBox.warning(self, "Backend no disponible", f"No se pudo conectar con {API_BASE}.\n\n{exc}")
            return
        if not response.ok:
            try:
                detail = response.json().get("detail", "No se pudo iniciar sesión.")
            except ValueError:
                detail = "No se pudo iniciar sesión."
            QMessageBox.warning(self, "Acceso rechazado", detail)
            return
        auth = response.json()
        if auth["user"]["role"] != selected_role:
            QMessageBox.warning(self, "Tipo de cuenta incorrecto", "Usa la pestaña correspondiente al tipo de cuenta.")
            return
        self.auth = auth
        self.accept()


class AdminApp(QMainWindow):
    """Panel restringido al administrador para profesores y asignaciones."""
    def __init__(self, token, user):
        super().__init__()
        self.token = token
        self.user = user
        self.professors = []
        self.classes = []
        self.setWindowTitle("AulaCheck · Administración")
        self.resize(1480, 850)
        self.setMinimumSize(1050, 700)
        root = QWidget()
        root.setObjectName("AdminRoot")
        layout = QVBoxLayout(root)
        layout.setContentsMargins(22, 14, 22, 20)
        layout.setSpacing(16)
        nav = QHBoxLayout()
        nav.setSpacing(8)
        self.professors_nav = QPushButton("Profesores")
        self.classes_nav = QPushButton("Clases y asignaciones")
        for button in (self.professors_nav, self.classes_nav):
            button.setObjectName("AdminTab")
            button.setCheckable(True)
            button.setMinimumHeight(46)
        self.professors_nav.setChecked(True)
        self.professors_nav.clicked.connect(lambda: self.show_admin_page(0))
        self.classes_nav.clicked.connect(lambda: self.show_admin_page(1))
        nav.addWidget(self.professors_nav)
        nav.addWidget(self.classes_nav)
        nav.addStretch()
        identity = QLabel(f"Administrador  ·  {user['email']}")
        identity.setObjectName("AdminIdentity")
        nav.addWidget(identity)
        logout = QPushButton("Cerrar sesión")
        logout.setObjectName("Logout")
        logout.clicked.connect(self.logout)
        nav.addWidget(logout)
        layout.addLayout(nav)
        self.tabs = QStackedWidget()
        self.tabs.addWidget(self.build_professor_tab())
        self.tabs.addWidget(self.build_classes_tab())
        layout.addWidget(self.tabs, 1)
        self.setCentralWidget(root)
        self.setStyleSheet("""
            QMainWindow, QWidget#AdminRoot { background:#F3F6FC; color:#172B4D; font-family:'Segoe UI'; font-size:13px; }
            QFrame#AdminCard { background:#FFFFFF; border:1px solid #DCE6F4; border-radius:11px; }
            QLabel#AdminSectionTitle { color:#172B4D; font-size:17px; font-weight:800; }
            QLabel#AdminFieldLabel { color:#283B5C; font-weight:600; }
            QLabel#AdminMuted { color:#788AA8; }
            QLabel#AdminCount { color:#587197; background:#EEF4FF; border-radius:13px; padding:5px 12px; }
            QLabel#AdminIdentity { color:#405677; padding:8px 12px; font-weight:600; }
            QLineEdit, QComboBox, QSpinBox, QTimeEdit { background:white; border:1px solid #CCD9EB; border-radius:7px; padding:9px 11px; min-height:20px; }
            QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QTimeEdit:focus { border:1px solid #3972ED; }
            QCheckBox { spacing:9px; color:#334967; }
            QTableWidget { background:white; alternate-background-color:#FAFBFE; border:1px solid #DCE6F4; border-radius:7px; gridline-color:transparent; selection-background-color:#E8F0FF; selection-color:#172B4D; }
            QTableWidget::item { border:0; border-bottom:1px solid #E8EEF7; padding:8px; }
            QHeaderView::section { background:#F5F8FD; color:#536988; border:0; border-bottom:1px solid #DCE6F4; padding:12px 9px; font-weight:700; text-align:left; }
            QPushButton { background:#EFF4FD; color:#245FE0; border:1px solid #DFE8F6; border-radius:7px; padding:10px 15px; font-weight:700; }
            QPushButton:hover { background:#E5EEFF; }
            QPushButton:disabled { color:#9AAAC0; background:#F5F7FB; border-color:#E5EAF2; }
            QPushButton#AdminTab { background:transparent; color:#536988; border:0; border-bottom:3px solid transparent; border-radius:0; padding:8px 15px; }
            QPushButton#AdminTab:checked { color:#2563EB; border-bottom:3px solid #3472EE; }
            QPushButton#Primary { background:#326BE8; color:white; border:0; padding:12px 20px; }
            QPushButton#Primary:hover { background:#285BCB; }
            QPushButton#Danger { color:#CB3434; background:#FFF2F2; border:1px solid #FFDADA; }
            QPushButton#Logout { background:#FFFFFF; border:1px solid #DCE6F4; }
            QCheckBox#SelectAll { color:#587197; font-weight:600; spacing:7px; }
            QMenu { background:white; border:1px solid #DCE6F4; padding:5px; }
            QMenu::item { padding:8px 24px; }
            QMenu::item:selected { background:#EEF4FF; color:#245FE0; }
        """)
        self.refresh_all()

    def api(self, method, path, **kwargs):
        return request_api(self.token, method, path, **kwargs)

    def show_admin_page(self, index):
        self.tabs.setCurrentIndex(index)
        self.professors_nav.setChecked(index == 0)
        self.classes_nav.setChecked(index == 1)

    @staticmethod
    def admin_card():
        card = QFrame()
        card.setObjectName("AdminCard")
        return card

    def build_professor_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(3, 3, 3, 0)
        layout.setSpacing(16)
        form = self.admin_card()
        form_layout = QVBoxLayout(form)
        form_layout.setContentsMargins(20, 18, 20, 18)
        form_layout.setSpacing(13)
        form_title = QLabel("Agregar profesor")
        form_title.setObjectName("AdminSectionTitle")
        form_layout.addWidget(form_title)
        fields = QGridLayout()
        fields.setHorizontalSpacing(18)
        fields.setVerticalSpacing(8)
        self.prof_email = QLineEdit()
        self.prof_email.setPlaceholderText("correo@institucion.edu")
        self.prof_password = QLineEdit()
        self.prof_password.setEchoMode(QLineEdit.Password)
        self.prof_password.setPlaceholderText("Contraseña inicial (mínimo 8 caracteres)")
        self.prof_password.setMinimumWidth(310)
        self.prof_active = QCheckBox("Activo desde la creación")
        self.prof_active.setChecked(True)
        create = QPushButton("Crear profesor")
        create.setObjectName("Primary")
        create.setMinimumHeight(44)
        create.clicked.connect(self.create_professor)
        email_label = QLabel("Correo institucional")
        email_label.setObjectName("AdminFieldLabel")
        password_label = QLabel("Contraseña inicial")
        password_label.setObjectName("AdminFieldLabel")
        fields.addWidget(email_label, 0, 0)
        fields.addWidget(password_label, 0, 1)
        fields.addWidget(self.prof_email, 1, 0)
        fields.addWidget(self.prof_password, 1, 1)
        fields.addWidget(create, 1, 2)
        fields.setColumnStretch(0, 5)
        fields.setColumnStretch(1, 5)
        fields.setColumnStretch(2, 2)
        form_layout.addLayout(fields)
        form_layout.addWidget(self.prof_active)
        layout.addWidget(form)

        list_card = self.admin_card()
        list_layout = QVBoxLayout(list_card)
        list_layout.setContentsMargins(19, 15, 19, 18)
        list_layout.setSpacing(12)
        tools_row = QHBoxLayout()
        list_title = QLabel("Profesores registrados")
        list_title.setObjectName("AdminSectionTitle")
        self.prof_count_label = QLabel("0 profesores")
        self.prof_count_label.setObjectName("AdminCount")
        tools_row.addWidget(list_title)
        tools_row.addWidget(self.prof_count_label)
        self.select_all_professors = QCheckBox("Seleccionar todos")
        self.select_all_professors.setObjectName("SelectAll")
        self.select_all_professors.toggled.connect(self.toggle_select_all_professors)
        tools_row.addWidget(self.select_all_professors)
        tools_row.addStretch()
        self.prof_search = QLineEdit()
        self.prof_search.setPlaceholderText("Buscar por correo...")
        self.prof_search.setClearButtonEnabled(True)
        self.prof_search.setMaximumWidth(300)
        self.prof_search.textChanged.connect(self.apply_professor_filters)
        tools_row.addWidget(self.prof_search)
        self.prof_filter_button = QPushButton("Filtrar")
        self.prof_filter_button.clicked.connect(self.show_professor_filter)
        tools_row.addWidget(self.prof_filter_button)
        list_layout.addLayout(tools_row)

        self.professor_filter = "Todos"
        self.prof_table = QTableWidget(0, 5)
        self.prof_table.setHorizontalHeaderLabels(["", "Correo institucional", "Estado", "Fecha de creación", "ID"])
        for column in range(1, 4):
            header_item = self.prof_table.horizontalHeaderItem(column)
            header_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.prof_table.horizontalHeaderItem(4).setTextAlignment(Qt.AlignCenter)
        self.prof_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)
        self.prof_table.setColumnWidth(0, 48)
        self.prof_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.prof_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Fixed)
        self.prof_table.setColumnWidth(2, 132)
        self.prof_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.prof_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.prof_table.verticalHeader().setVisible(False)
        self.prof_table.verticalHeader().setDefaultSectionSize(50)
        self.prof_table.setAlternatingRowColors(True)
        self.prof_table.horizontalHeader().setStretchLastSection(False)
        self.prof_table.horizontalHeader().setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.prof_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.prof_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.prof_table.setShowGrid(False)
        self.prof_table.itemSelectionChanged.connect(self.update_professor_actions)
        self.prof_table.itemChanged.connect(self.update_professor_actions)
        list_layout.addWidget(self.prof_table, 1)
        self.prof_empty_label = QLabel()
        self.prof_empty_label.setObjectName("AdminMuted")
        self.prof_empty_label.setAlignment(Qt.AlignCenter)
        self.prof_empty_label.setMinimumHeight(42)
        self.prof_empty_label.hide()
        list_layout.addWidget(self.prof_empty_label)
        layout.addWidget(list_card, 1)

        action_card = self.admin_card()
        action_layout = QHBoxLayout(action_card)
        action_layout.setContentsMargins(16, 14, 16, 14)
        action_layout.setSpacing(14)
        self.professor_action_buttons = {}
        for key, label, slot, name in (("toggle", "Activar / desactivar", self.toggle_professor, ""), ("password", "Cambiar contraseña", self.change_password, ""), ("delete", "Eliminar profesor", self.delete_professor, "Danger")):
            button = QPushButton(label)
            if name:
                button.setObjectName(name)
            button.setMinimumHeight(44)
            button.clicked.connect(slot)
            action_layout.addWidget(button, 1)
            self.professor_action_buttons[key] = button
            button.setEnabled(False)
        refresh = QPushButton("Actualizar")
        refresh.setMinimumHeight(44)
        refresh.clicked.connect(self.refresh_professors)
        action_layout.addWidget(refresh, 1)
        layout.addWidget(action_card)
        return page

    def build_classes_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(3, 3, 3, 0)
        layout.setSpacing(16)
        form = self.admin_card()
        grid = QGridLayout(form)
        grid.setContentsMargins(20, 18, 20, 18)
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(9)
        grid.addWidget(QLabel("CREAR CLASE Y ASIGNAR PROFESOR"), 0, 0, 1, 5)
        self.class_name = QLineEdit()
        self.class_name.setPlaceholderText("Nombre de la clase")
        self.class_time = QTimeEdit()
        self.class_time.setDisplayFormat("HH:mm")
        self.class_time.setTime(QTime(8, 0))
        self.class_tolerance = QSpinBox()
        self.class_tolerance.setRange(0, 180)
        self.class_tolerance.setValue(10)
        self.class_professor = QComboBox()
        create = QPushButton("Crear clase")
        create.setObjectName("Primary")
        create.setMinimumHeight(42)
        create.clicked.connect(self.create_class)
        grid.addWidget(QLabel("Nombre"), 1, 0)
        grid.addWidget(self.class_name, 1, 1)
        grid.addWidget(QLabel("Hora"), 1, 2)
        grid.addWidget(self.class_time, 1, 3)
        grid.addWidget(QLabel("Tolerancia"), 2, 0)
        grid.addWidget(self.class_tolerance, 2, 1)
        grid.addWidget(QLabel("Profesor"), 2, 2)
        grid.addWidget(self.class_professor, 2, 3)
        grid.addWidget(create, 1, 4, 2, 1)
        layout.addWidget(form)
        note = QLabel("Cada clase tiene un profesor asignado. Un profesor puede tener varias clases.")
        note.setObjectName("AdminMuted")
        layout.addWidget(note)
        self.class_table = QTableWidget(0, 6)
        self.class_table.setHorizontalHeaderLabels(["NRC", "Clase", "Hora", "Profesor actual", "Reasignar a", "Acción"])
        self.class_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.class_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.class_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.class_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.class_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        self.class_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)
        self.class_table.horizontalHeader().setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.class_table.verticalHeader().setVisible(False)
        self.class_table.verticalHeader().setDefaultSectionSize(46)
        self.class_table.setAlternatingRowColors(True)
        self.class_table.setShowGrid(False)
        self.class_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        layout.addWidget(self.class_table, 1)
        refresh = QPushButton("Actualizar clases")
        refresh.clicked.connect(self.refresh_classes)
        layout.addWidget(refresh, alignment=Qt.AlignRight)
        return page

    def run(self, fn, success=None):
        try:
            result = fn()
            if success:
                QMessageBox.information(self, "AulaCheck", success)
            return result
        except ApiError as exc:
            QMessageBox.warning(self, "No se pudo completar", str(exc))
            return None

    def refresh_all(self):
        self.refresh_professors()

    def refresh_professors(self):
        result = self.run(lambda: self.api("GET", "/admin/professors"))
        if result is None:
            return
        self.professors = result
        self.prof_table.blockSignals(True)
        self.prof_table.setRowCount(len(result))
        for row, p in enumerate(result):
            selected = QTableWidgetItem()
            selected.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsUserCheckable)
            selected.setCheckState(Qt.Unchecked)
            selected.setTextAlignment(Qt.AlignCenter)
            self.prof_table.setItem(row, 0, selected)

            email_item = QTableWidgetItem(p["email"])
            email_item.setData(Qt.UserRole, p["id"])
            self.prof_table.setItem(row, 1, email_item)

            state_item = QTableWidgetItem("Activo" if p["is_active"] else "Inactivo")
            state_item.setTextAlignment(Qt.AlignCenter)
            state_item.setForeground(QColor("#16803C" if p["is_active"] else "#B42318"))
            state_item.setBackground(QColor("#E7F6EC" if p["is_active"] else "#FFF0EF"))
            state_item.setFont(QFont("Segoe UI", 9, QFont.Bold))
            self.prof_table.setItem(row, 2, state_item)

            created = str(p["created_at"]).split("T")[0]
            try:
                created_date = datetime.strptime(created, "%Y-%m-%d")
                months = ("ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic")
                created = f"{created_date.day} {months[created_date.month - 1]} {created_date.year}"
            except ValueError:
                pass
            self.prof_table.setItem(row, 3, QTableWidgetItem(created))
            id_item = QTableWidgetItem(str(p["id"]))
            id_item.setTextAlignment(Qt.AlignCenter)
            self.prof_table.setItem(row, 4, id_item)
        self.prof_table.blockSignals(False)
        self.select_all_professors.blockSignals(True)
        self.select_all_professors.setChecked(False)
        self.select_all_professors.blockSignals(False)
        self.prof_count_label.setText(f'{len(result)} profesor{"es" if len(result) != 1 else ""}')
        self.apply_professor_filters()
        self.class_professor.clear()
        for p in self.professors:
            if p["is_active"]:
                self.class_professor.addItem(p["email"], p["id"])
        self.refresh_classes()

    def apply_professor_filters(self, *_):
        if not hasattr(self, "prof_table"):
            return
        search = self.prof_search.text().strip().casefold()
        visible_count = 0
        for row, professor in enumerate(self.professors):
            matches_text = search in professor["email"].casefold()
            matches_state = (
                self.professor_filter == "Todos"
                or (self.professor_filter == "Activos" and professor["is_active"])
                or (self.professor_filter == "Inactivos" and not professor["is_active"])
            )
            visible = matches_text and matches_state
            self.prof_table.setRowHidden(row, not visible)
            visible_count += int(visible)
        if hasattr(self, "prof_empty_label"):
            if not self.professors:
                self.prof_empty_label.setText("Aún no hay profesores registrados. Agrega una cuenta en el formulario superior.")
            else:
                self.prof_empty_label.setText("No hay profesores que coincidan con la búsqueda o el filtro actual.")
            self.prof_empty_label.setVisible(visible_count == 0)
        self.update_professor_actions()

    def toggle_select_all_professors(self, checked):
        if not hasattr(self, "prof_table"):
            return
        for row in range(self.prof_table.rowCount()):
            if self.prof_table.isRowHidden(row):
                continue
            item = self.prof_table.item(row, 0)
            if item is not None:
                item.setCheckState(Qt.Checked if checked else Qt.Unchecked)
        self.update_professor_actions()

    def selected_professors(self):
        checked = []
        for row, professor in enumerate(self.professors):
            if self.prof_table.isRowHidden(row):
                continue
            item = self.prof_table.item(row, 0)
            if item is not None and item.checkState() == Qt.Checked:
                checked.append(professor)
        if checked:
            return checked
        row = self.prof_table.currentRow()
        if 0 <= row < len(self.professors) and not self.prof_table.isRowHidden(row):
            return [self.professors[row]]
        return []

    def update_professor_actions(self, *_):
        if not hasattr(self, "professor_action_buttons"):
            return
        selected = self.selected_professors()
        count = len(selected)
        self.professor_action_buttons["toggle"].setEnabled(count > 0)
        self.professor_action_buttons["delete"].setEnabled(count > 0)
        self.professor_action_buttons["password"].setEnabled(count == 1)
        self.professor_action_buttons["toggle"].setText("Activar / desactivar" if count <= 1 else f"Cambiar estado ({count})")
        self.professor_action_buttons["delete"].setText("Eliminar profesor" if count <= 1 else f"Eliminar {count} profesores")
        self.professor_action_buttons["password"].setToolTip("Selecciona un solo profesor para cambiar su contraseña.")
        visible_items = [
            self.prof_table.item(row, 0)
            for row in range(self.prof_table.rowCount())
            if not self.prof_table.isRowHidden(row) and self.prof_table.item(row, 0) is not None
        ]
        all_checked = bool(visible_items) and all(item.checkState() == Qt.Checked for item in visible_items)
        self.select_all_professors.blockSignals(True)
        self.select_all_professors.setChecked(all_checked)
        self.select_all_professors.blockSignals(False)

    def show_professor_filter(self):
        menu = QMenu(self)
        for label in ("Todos", "Activos", "Inactivos"):
            action = menu.addAction(label)
            action.triggered.connect(lambda checked=False, value=label: self.set_professor_filter(value))
        menu.exec(self.prof_filter_button.mapToGlobal(self.prof_filter_button.rect().bottomLeft()))

    def set_professor_filter(self, value):
        self.professor_filter = value
        self.prof_filter_button.setText(value if value != "Todos" else "Filtrar")
        self.apply_professor_filters()

    def selected_professor(self):
        selected = self.selected_professors()
        if not selected:
            QMessageBox.information(self, "Selecciona un profesor", "Selecciona primero una fila de la tabla.")
            return None
        if len(selected) > 1:
            QMessageBox.information(self, "Selecciona uno solo", "Esta acción requiere seleccionar un único profesor.")
            return None
        return selected[0]

    def create_professor(self):
        email, password = self.prof_email.text().strip(), self.prof_password.text()
        if not email or len(password) < 8:
            QMessageBox.warning(self, "Datos incompletos", "Indica un correo y una contraseña de al menos 8 caracteres.")
            return
        p = self.run(lambda: self.api("POST", "/admin/professors", json={
            "email": email, "password": password, "is_active": self.prof_active.isChecked()
        }), "Cuenta de profesor creada.")
        if p:
            self.prof_email.clear()
            self.prof_password.clear()
            self.refresh_professors()

    def toggle_professor(self):
        selected = self.selected_professors()
        if not selected:
            return
        try:
            for professor in selected:
                active = not professor["is_active"]
                self.api("PATCH", f'/admin/professors/{professor["id"]}/status', json={"is_active": active})
        except ApiError as exc:
            QMessageBox.warning(self, "No se pudo cambiar el estado", str(exc))
            self.refresh_professors()
            return
        QMessageBox.information(self, "AulaCheck", f"Estado actualizado para {len(selected)} profesor(es).")
        self.refresh_professors()

    def change_password(self):
        p = self.selected_professor()
        if not p:
            return
        password, ok = QInputDialog.getText(self, "Cambiar contraseña", f'Nueva contraseña para {p["email"]}:', QLineEdit.Password)
        if not ok:
            return
        if len(password) < 8:
            QMessageBox.warning(self, "Contraseña inválida", "Debe tener al menos 8 caracteres.")
            return
        self.run(lambda: self.api("PUT", f'/admin/professors/{p["id"]}/password', json={"password": password}), "Contraseña actualizada.")

    def delete_professor(self):
        selected = self.selected_professors()
        if not selected:
            return
        emails = ", ".join(p["email"] for p in selected)
        answer = QMessageBox.question(
            self, "Eliminar profesor(es)",
            f'¿Eliminar {emails}? Las clases quedarán sin asignar y conservarán sus datos.'
        )
        if answer != QMessageBox.Yes:
            return
        try:
            for professor in selected:
                self.api("DELETE", f'/admin/professors/{professor["id"]}')
        except ApiError as exc:
            QMessageBox.warning(self, "No se pudo eliminar", str(exc))
            self.refresh_professors()
            return
        QMessageBox.information(self, "AulaCheck", f"Se eliminaron {len(selected)} profesor(es).")
        self.refresh_professors()

    def refresh_classes(self):
        if not hasattr(self, "class_table"):
            return
        result = self.run(lambda: self.api("GET", "/classes"))
        if result is None:
            return
        self.classes = result
        self.class_table.setRowCount(len(result))
        for row, course in enumerate(result):
            for col, value in enumerate([course["nrc"], course["name"], str(course["start_time"])[:5], course.get("professor_email") or "Sin asignar"]):
                self.class_table.setItem(row, col, QTableWidgetItem(str(value)))
            combo = QComboBox()
            for p in self.professors:
                if p["is_active"]:
                    combo.addItem(p["email"], p["id"])
            current_id = course.get("professor_id")
            if current_id is not None:
                idx = combo.findData(current_id)
                if idx >= 0:
                    combo.setCurrentIndex(idx)
            self.class_table.setCellWidget(row, 4, combo)
            button = QPushButton("Asignar")
            button.setMinimumHeight(36)
            button.setMinimumWidth(84)
            button.clicked.connect(lambda checked=False, r=row, c=combo: self.assign_professor(r, c))
            self.class_table.setCellWidget(row, 5, button)

    def create_class(self):
        if self.class_professor.currentIndex() < 0:
            QMessageBox.warning(self, "Sin profesores", "Crea y activa al menos un profesor antes de crear clases.")
            return
        name = self.class_name.text().strip()
        if len(name) < 2:
            QMessageBox.warning(self, "Nombre inválido", "El nombre debe tener al menos 2 caracteres.")
            return
        course = self.run(lambda: self.api("POST", "/classes", json={
            "name": name, "start_time": self.class_time.time().toString("HH:mm:ss"),
            "tolerance_minutes": self.class_tolerance.value(), "professor_id": self.class_professor.currentData()
        }), "Clase creada y asignada.")
        if course:
            self.class_name.clear()
            self.refresh_classes()

    def assign_professor(self, row, combo):
        if combo.currentIndex() < 0:
            QMessageBox.warning(self, "Sin profesores activos", "Activa un profesor antes de asignar la clase.")
            return
        course = self.classes[row]
        if self.run(lambda: self.api("PATCH", f'/admin/classes/{course["nrc"]}/professor', json={"professor_id": combo.currentData()}),
                    f'Clase NRC {course["nrc"]} asignada correctamente.'):
            self.refresh_classes()

    def logout(self):
        self.token = ""
        self.close()


def run_desktop():
    app = QApplication(sys.argv)
    app.setFont(QFont("Segoe UI", 10))
    while True:
        login = LoginDialog()
        if login.exec() != QDialog.Accepted or not login.auth:
            break
        auth = login.auth
        window = AdminApp(auth["access_token"], auth["user"]) if auth["user"]["role"] == "admin" else AulaCheckApp(auth["access_token"], auth["user"])
        window.showMaximized()
        app.exec()
        if not window.token:
            continue
        break
    return 0


if __name__ == "__main__":
    sys.exit(run_desktop())
