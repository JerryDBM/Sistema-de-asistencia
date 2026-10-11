import sys
import csv
from datetime import datetime
from PySide6.QtCore import Qt, QTime
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QFrame, QTableWidget, QTableWidgetItem, QHeaderView,
    QLineEdit, QComboBox, QSpinBox, QTimeEdit, QMessageBox, QAbstractItemView,
    QFileDialog, QInputDialog, QStackedWidget, QFormLayout, QDialog,
    QDialogButtonBox, QTextEdit
)


class AttendanceApp(QMainWindow):
    """Prototipo de interfaz PySide6. Los datos son locales y de demostración."""
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AulaCheck | Sistema de asistencia académica")
        self.resize(1360, 860)
        self.setMinimumSize(1120, 720)
        self.session_active = False
        self.classes = [
            {"name": "Computación e Interfaces", "start": "08:00", "tolerance": 10,
             "students": ["Ana Martínez", "Carlos Pérez", "Laura Gómez", "Andrés Torres",
                          "Valentina Ruiz", "Daniel Herrera", "Sofía Castro", "Mateo Díaz"]}
        ]
        self.current_class = 0
        self.students = [
            {"name":"Ana Martínez", "email":"ana.martinez@utb.edu.co", "time":"08:02", "status":"Presente"},
            {"name":"Carlos Pérez", "email":"carlos.perez@utb.edu.co", "time":"08:05", "status":"Presente"},
            {"name":"Laura Gómez", "email":"laura.gomez@utb.edu.co", "time":"08:09", "status":"Presente"},
            {"name":"Andrés Torres", "email":"andres.torres@utb.edu.co", "time":"08:17", "status":"Tarde"},
            {"name":"Valentina Ruiz", "email":"valentina.ruiz@utb.edu.co", "time":"08:03", "status":"Presente"},
            {"name":"Daniel Herrera", "email":"daniel.herrera@utb.edu.co", "time":"—", "status":"Pendiente"},
            {"name":"Sofía Castro", "email":"sofia.castro@utb.edu.co", "time":"08:04", "status":"Presente"},
            {"name":"Mateo Díaz", "email":"mateo.diaz@utb.edu.co", "time":"—", "status":"Pendiente"},
        ]
        self.all_students = [
            ("Ana Martínez","ana.martinez@utb.edu.co"),
            ("Carlos Pérez","carlos.perez@utb.edu.co"),
            ("Laura Gómez","laura.gomez@utb.edu.co"),
            ("Andrés Torres","andres.torres@utb.edu.co"),
            ("Valentina Ruiz","valentina.ruiz@utb.edu.co"),
            ("Daniel Herrera","daniel.herrera@utb.edu.co"),
            ("Sofía Castro","sofia.castro@utb.edu.co"),
            ("Mateo Díaz","mateo.diaz@utb.edu.co"),
        ]
        self.setStyleSheet("""
            QMainWindow, QWidget { background:#F4F7FB; color:#172033; font-family:'Segoe UI'; }
            QFrame#Sidebar { background:#152238; border-radius:16px; }
            QLabel#Brand { color:white; font-size:23px; font-weight:800; }
            QLabel#SideCaption { color:#9FAFC6; font-size:10px; font-weight:800; letter-spacing:1px; }
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
            QLineEdit, QComboBox, QSpinBox, QTimeEdit, QTextEdit {
                background:white; border:1px solid #D8DFEA; border-radius:7px; padding:8px; min-height:18px;
            }
            QTableWidget { background:white; border:none; gridline-color:#EDF0F5;
                selection-background-color:#E8EEFF; selection-color:#172033; }
            QHeaderView::section { background:#F7F9FC; color:#657189; border:none;
                border-bottom:1px solid #E5EAF2; padding:11px; font-weight:700; }
        """)

        root = QWidget()
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(18,18,18,18)
        root_layout.setSpacing(18)

        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(228)
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(16,22,16,18)
        side.setSpacing(8)
        brand = QLabel("◈ AulaCheck")
        brand.setObjectName("Brand")
        side.addWidget(brand)
        tagline = QLabel("ASISTENCIA ACADÉMICA")
        tagline.setObjectName("SideCaption")
        side.addWidget(tagline)
        side.addSpacing(20)
        section = QLabel("MENÚ PRINCIPAL")
        section.setObjectName("SideCaption")
        side.addWidget(section)

        self.nav_buttons = []
        nav_items = [
            ("▦   Panel de asistencia", 0),
            ("▣   Gestión de clases", 1),
            ("♙   Estudiantes", 2),
            ("◷   Historial", 3),
            ("ⓘ   Acerca de", 4),
        ]
        for text, index in nav_items:
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
        dv.setContentsMargins(12,12,12,12)
        d1 = QLabel("ESTACIÓN DE LECTURA")
        d1.setStyleSheet("color:#9FAFC6;font-size:10px;font-weight:800;")
        self.device_status = QLabel("●  ESP32-CAM en espera")
        self.device_status.setStyleSheet("color:#F6D98B;font-size:12px;font-weight:700;")
        d2 = QLabel("Estado de demostración")
        d2.setStyleSheet("color:#D8E1EF;font-size:11px;")
        dv.addWidget(d1); dv.addWidget(self.device_status); dv.addWidget(d2)
        side.addWidget(device)

        main_area = QWidget()
        main_layout = QVBoxLayout(main_area)
        main_layout.setContentsMargins(0,0,0,0)
        main_layout.setSpacing(14)
        self.stack = QStackedWidget()
        self.pages = [
            self.build_dashboard(),
            self.build_classes_page(),
            self.build_students_page(),
            self.build_history_page(),
            self.build_about_page()
        ]
        for page in self.pages:
            self.stack.addWidget(page)
        main_layout.addWidget(self.stack)
        root_layout.addWidget(sidebar)
        root_layout.addWidget(main_area,1)
        self.setCentralWidget(root)
        self.refresh_attendance_table()
        self.refresh_class_table()
        self.refresh_students_table()
        self.refresh_history_table()

    def label(self, text, name=None):
        l = QLabel(text)
        if name:
            l.setObjectName(name)
        return l

    def section_label(self, text):
        l = QLabel(text)
        l.setStyleSheet("font-size:11px;font-weight:800;color:#6B778C;letter-spacing:1px;")
        return l

    def panel(self):
        f = QFrame()
        f.setObjectName("Panel")
        return f

    def page_header(self, title, subtitle):
        row = QHBoxLayout()
        col = QVBoxLayout()
        t = QLabel(title); t.setObjectName("PageTitle")
        s = QLabel(subtitle); s.setObjectName("Muted")
        col.addWidget(t); col.addWidget(s)
        row.addLayout(col); row.addStretch()
        row.addWidget(QLabel(datetime.now().strftime("%d/%m/%Y")))
        return row

    def metric_card(self, title, value):
        card = QFrame(); card.setObjectName("Card")
        lay = QVBoxLayout(card); lay.setContentsMargins(15,13,15,13)
        t = QLabel(title); t.setObjectName("MetricTitle")
        v = QLabel(str(value)); v.setObjectName("MetricValue")
        lay.addWidget(t); lay.addWidget(v)
        card.value_label = v
        return card

    def build_dashboard(self):
        page = QWidget(); layout = QVBoxLayout(page); layout.setContentsMargins(0,0,0,0); layout.setSpacing(14)
        layout.addLayout(self.page_header("Panel de asistencia","Administra la sesión y consulta el estado de cada estudiante."))
        config = self.panel(); cg = QGridLayout(config); cg.setContentsMargins(16,13,16,13); cg.setSpacing(10)
        cg.addWidget(self.section_label("INFORMACIÓN DE LA CLASE"),0,0,1,6)
        self.course_combo = QComboBox()
        self.course_combo.addItems([c["name"] for c in self.classes])
        self.course_combo.currentIndexChanged.connect(self.change_current_class)
        self.start_time = QTimeEdit(); self.start_time.setDisplayFormat("HH:mm"); self.start_time.setTime(QTime(8,0))
        self.tolerance = QSpinBox(); self.tolerance.setRange(0,180); self.tolerance.setValue(10); self.tolerance.setSuffix(" min")
        cg.addWidget(QLabel("Asignatura"),1,0); cg.addWidget(self.course_combo,2,0,1,2)
        cg.addWidget(QLabel("Hora de inicio"),1,2); cg.addWidget(self.start_time,2,2)
        cg.addWidget(QLabel("Tolerancia"),1,3); cg.addWidget(self.tolerance,2,3)
        self.save_config_btn = QPushButton("Guardar configuración"); self.save_config_btn.setObjectName("Secondary")
        self.save_config_btn.clicked.connect(self.save_current_config)
        cg.addWidget(self.save_config_btn,2,4,1,2)
        layout.addWidget(config)

        cards = QHBoxLayout()
        self.metric_total = self.metric_card("Estudiantes de la clase", len(self.students))
        self.metric_present = self.metric_card("Asistencia válida", 0)
        self.metric_late = self.metric_card("Fuera de tolerancia", 0)
        self.metric_pending = self.metric_card("Pendientes", len(self.students))
        for c in [self.metric_total,self.metric_present,self.metric_late,self.metric_pending]:
            cards.addWidget(c)
        layout.addLayout(cards)

        table_panel = self.panel(); tp = QVBoxLayout(table_panel); tp.setContentsMargins(15,13,15,14)
        header = QHBoxLayout()
        header.addWidget(self.section_label("LISTA DE ASISTENCIA"))
        header.addStretch()
        self.search_attendance = QLineEdit(); self.search_attendance.setPlaceholderText("Buscar estudiante...")
        self.search_attendance.setMaximumWidth(220); self.search_attendance.textChanged.connect(self.filter_attendance)
        header.addWidget(self.search_attendance)
        tp.addLayout(header)
        self.attendance_table = QTableWidget(0,4)
        self.attendance_table.setHorizontalHeaderLabels(["Nombre del estudiante","Correo institucional","Hora de registro","Estado"])
        self.attendance_table.horizontalHeader().setSectionResizeMode(0,QHeaderView.Stretch)
        self.attendance_table.horizontalHeader().setSectionResizeMode(1,QHeaderView.Stretch)
        self.attendance_table.horizontalHeader().setSectionResizeMode(2,QHeaderView.ResizeToContents)
        self.attendance_table.horizontalHeader().setSectionResizeMode(3,QHeaderView.ResizeToContents)
        self.attendance_table.verticalHeader().setVisible(False)
        self.attendance_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.attendance_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.attendance_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.attendance_table.setAlternatingRowColors(True)
        tp.addWidget(self.attendance_table,1)
        actions = QHBoxLayout()
        self.session_label = QLabel("● Sesión no iniciada")
        self.session_label.setStyleSheet("color:#6B778C;font-weight:700;")
        actions.addWidget(self.session_label); actions.addStretch()
        self.start_btn = QPushButton("▶  Iniciar asistencia"); self.start_btn.setObjectName("Success")
        self.start_btn.clicked.connect(self.start_session)
        self.finish_btn = QPushButton("■  Finalizar clase"); self.finish_btn.setObjectName("Danger")
        self.finish_btn.clicked.connect(self.finish_session); self.finish_btn.setEnabled(False)
        self.manual_btn = QPushButton("＋ Añadir asistencia"); self.manual_btn.setObjectName("Secondary")
        self.manual_btn.clicked.connect(self.manual_attendance)
        self.export_btn = QPushButton("⇩  Guardar / exportar"); self.export_btn.setObjectName("Primary")
        self.export_btn.clicked.connect(self.export_attendance)
        for b in [self.start_btn,self.finish_btn,self.manual_btn,self.export_btn]: actions.addWidget(b)
        tp.addLayout(actions)
        layout.addWidget(table_panel,1)
        return page

    def build_classes_page(self):
        page=QWidget(); layout=QVBoxLayout(page); layout.setContentsMargins(0,0,0,0); layout.setSpacing(14)
        layout.addLayout(self.page_header("Gestión de clases","Crea asignaturas y configura el horario y la tolerancia."))
        form=self.panel(); grid=QGridLayout(form); grid.setContentsMargins(18,18,18,18); grid.setSpacing(10)
        grid.addWidget(self.section_label("NUEVA CLASE"),0,0,1,4)
        self.new_class_name=QLineEdit(); self.new_class_name.setPlaceholderText("Ej. Computación e Interfaces")
        self.new_class_start=QTimeEdit(); self.new_class_start.setDisplayFormat("HH:mm"); self.new_class_start.setTime(QTime(8,0))
        self.new_class_tolerance=QSpinBox(); self.new_class_tolerance.setRange(0,180); self.new_class_tolerance.setValue(10); self.new_class_tolerance.setSuffix(" min")
        grid.addWidget(QLabel("Nombre de la clase"),1,0); grid.addWidget(self.new_class_name,2,0,1,2)
        grid.addWidget(QLabel("Hora de inicio"),1,2); grid.addWidget(self.new_class_start,2,2)
        grid.addWidget(QLabel("Tolerancia"),1,3); grid.addWidget(self.new_class_tolerance,2,3)
        add=QPushButton("Crear clase"); add.setObjectName("Primary"); add.clicked.connect(self.add_class)
        grid.addWidget(add,2,4)
        layout.addWidget(form)
        table_panel=self.panel(); tl=QVBoxLayout(table_panel); tl.setContentsMargins(16,14,16,16)
        tl.addWidget(self.section_label("CLASES REGISTRADAS"))
        self.classes_table=QTableWidget(0,3)
        self.classes_table.setHorizontalHeaderLabels(["Asignatura","Hora de inicio","Tolerancia"])
        self.classes_table.horizontalHeader().setSectionResizeMode(0,QHeaderView.Stretch)
        self.classes_table.horizontalHeader().setSectionResizeMode(1,QHeaderView.ResizeToContents)
        self.classes_table.horizontalHeader().setSectionResizeMode(2,QHeaderView.ResizeToContents)
        self.classes_table.verticalHeader().setVisible(False); self.classes_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.classes_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        tl.addWidget(self.classes_table)
        select=QPushButton("Usar clase seleccionada en el panel de asistencia"); select.setObjectName("Secondary")
        select.clicked.connect(self.use_selected_class); tl.addWidget(select,alignment=Qt.AlignRight)
        layout.addWidget(table_panel,1)
        return page

    def build_students_page(self):
        page=QWidget(); layout=QVBoxLayout(page); layout.setContentsMargins(0,0,0,0); layout.setSpacing(14)
        layout.addLayout(self.page_header("Estudiantes","Consulta el listado y agrega estudiantes a la clase actual."))
        form=self.panel(); grid=QGridLayout(form); grid.setContentsMargins(18,18,18,18); grid.setSpacing(10)
        grid.addWidget(self.section_label("AÑADIR ESTUDIANTE"),0,0,1,4)
        self.student_name=QLineEdit(); self.student_name.setPlaceholderText("Nombre y apellidos")
        self.student_email=QLineEdit(); self.student_email.setPlaceholderText("nombre@utb.edu.co")
        grid.addWidget(QLabel("Nombre"),1,0); grid.addWidget(self.student_name,2,0,1,2)
        grid.addWidget(QLabel("Correo institucional"),1,2); grid.addWidget(self.student_email,2,2,1,2)
        add=QPushButton("Añadir a la clase"); add.setObjectName("Primary"); add.clicked.connect(self.add_student)
        grid.addWidget(add,2,4)
        layout.addWidget(form)
        panel=self.panel(); pl=QVBoxLayout(panel); pl.setContentsMargins(16,14,16,16)
        top=QHBoxLayout(); top.addWidget(self.section_label("LISTA DE ESTUDIANTES")); top.addStretch()
        self.student_search=QLineEdit(); self.student_search.setPlaceholderText("Buscar por nombre o correo"); self.student_search.setMaximumWidth(270)
        self.student_search.textChanged.connect(self.filter_students); top.addWidget(self.student_search); pl.addLayout(top)
        self.students_table=QTableWidget(0,2); self.students_table.setHorizontalHeaderLabels(["Nombre","Correo institucional"])
        self.students_table.horizontalHeader().setSectionResizeMode(0,QHeaderView.Stretch); self.students_table.horizontalHeader().setSectionResizeMode(1,QHeaderView.Stretch)
        self.students_table.verticalHeader().setVisible(False); self.students_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        pl.addWidget(self.students_table); layout.addWidget(panel,1)
        return page

    def build_history_page(self):
        page=QWidget(); layout=QVBoxLayout(page); layout.setContentsMargins(0,0,0,0); layout.setSpacing(14)
        layout.addLayout(self.page_header("Historial de asistencia","Vista demostrativa de sesiones y registros anteriores."))
        panel=self.panel(); pl=QVBoxLayout(panel); pl.setContentsMargins(16,16,16,16)
        pl.addWidget(self.section_label("REGISTROS RECIENTES"))
        self.history_table=QTableWidget(0,4); self.history_table.setHorizontalHeaderLabels(["Clase","Fecha","Estudiantes registrados","Estado"])
        self.history_table.horizontalHeader().setSectionResizeMode(0,QHeaderView.Stretch)
        for i in range(1,4): self.history_table.horizontalHeader().setSectionResizeMode(i,QHeaderView.ResizeToContents)
        self.history_table.verticalHeader().setVisible(False); self.history_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        pl.addWidget(self.history_table)
        info=QLabel("Los datos de esta pantalla son ilustrativos. Al conectar FastAPI y MySQL se mostrarán sesiones guardadas.")
        info.setObjectName("Muted"); pl.addWidget(info)
        layout.addWidget(panel,1)
        return page

    def build_about_page(self):
        page=QWidget(); layout=QVBoxLayout(page); layout.setContentsMargins(0,0,0,0); layout.setSpacing(14)
        layout.addLayout(self.page_header("Acerca del proyecto","Quiénes somos, qué hacemos y qué valor aportamos."))
        panel=self.panel(); pl=QVBoxLayout(panel); pl.setContentsMargins(26,24,26,24); pl.setSpacing(12)
        title=QLabel("AulaCheck · Asistencia académica mediante QR dinámicos")
        title.setStyleSheet("font-size:20px;font-weight:800;color:#17365D;")
        pl.addWidget(title)
        desc=QLabel("Somos un equipo de estudiantes que integra programación, interfaces y electrónica para facilitar el registro de asistencia. Nuestra solución combina una aplicación móvil en Flutter, una estación ESP32-CAM, un backend en FastAPI, una base de datos MySQL y una interfaz de escritorio en PySide6.")
        desc.setWordWrap(True); pl.addWidget(desc)
        pl.addWidget(self.section_label("¿QUÉ APORTAMOS?"))
        value=QLabel("Reducimos tareas manuales, centralizamos los registros y damos retroalimentación inmediata al estudiante y al profesor. El sistema valida la identidad, la vigencia del token y el tiempo de tolerancia de cada clase.")
        value.setWordWrap(True); pl.addWidget(value)
        pl.addWidget(self.section_label("INTEGRANTES"))
        for name in ["Fredy Jarava Chavez","Jerry Buelvas Mejia","Juan Caicedo Gomez","Rafael Villero Castillo"]:
            pl.addWidget(QLabel("•  "+name))
        pl.addStretch()
        layout.addWidget(panel,1)
        return page

    def navigate(self, index):
        self.stack.setCurrentIndex(index)
        for i,b in enumerate(self.nav_buttons): b.setChecked(i==index)
        if index==0:
            self.refresh_attendance_table()
        elif index==1:
            self.refresh_class_table()
        elif index==2:
            self.refresh_students_table()
        elif index==3:
            self.refresh_history_table()

    def change_current_class(self, index):
        if index < 0 or index >= len(self.classes): return
        self.current_class=index
        c=self.classes[index]
        self.start_time.setTime(QTime.fromString(c["start"],"HH:mm"))
        self.tolerance.setValue(c["tolerance"])
        class_names=set(c["students"])
        # Rebuild current roster using stored sample profiles where possible
        known={name:(name,email) for name,email in self.all_students}
        new_rows=[]
        for name in c["students"]:
            email=known.get(name,(name,name.lower().replace(" ",".")+"@utb.edu.co"))[1]
            existing=next((s for s in self.students if s["name"]==name),None)
            new_rows.append(existing.copy() if existing else {"name":name,"email":email,"time":"—","status":"Pendiente"})
        self.students=new_rows
        self.refresh_attendance_table()
        self.refresh_students_table()

    def save_current_config(self):
        c=self.classes[self.current_class]
        c["start"]=self.start_time.time().toString("HH:mm")
        c["tolerance"]=self.tolerance.value()
        QMessageBox.information(self,"Configuración guardada","Se guardó localmente la configuración de demostración. La conexión con FastAPI se implementará después.")

    def add_class(self):
        name=self.new_class_name.text().strip()
        if not name:
            QMessageBox.warning(self,"Falta el nombre","Escribe el nombre de la clase.")
            return
        if any(c["name"].lower()==name.lower() for c in self.classes):
            QMessageBox.warning(self,"Clase existente","Ya hay una clase con ese nombre.")
            return
        self.classes.append({"name":name,"start":self.new_class_start.time().toString("HH:mm"),
                             "tolerance":self.new_class_tolerance.value(),"students":[]})
        self.course_combo.addItem(name)
        self.new_class_name.clear()
        self.refresh_class_table()
        QMessageBox.information(self,"Clase creada",f"Se creó «{name}» en los datos locales de demostración.")

    def refresh_class_table(self):
        if not hasattr(self,"classes_table"): return
        self.classes_table.setRowCount(len(self.classes))
        for r,c in enumerate(self.classes):
            vals=[c["name"],c["start"],f'{c["tolerance"]} min']
            for col,val in enumerate(vals): self.classes_table.setItem(r,col,QTableWidgetItem(val))

    def use_selected_class(self):
        row=self.classes_table.currentRow()
        if row<0:
            QMessageBox.information(self,"Selecciona una clase","Selecciona una fila de la tabla.")
            return
        self.course_combo.setCurrentIndex(row)
        self.navigate(0)

    def add_student(self):
        name=self.student_name.text().strip()
        email=self.student_email.text().strip()
        if not name or not email or "@" not in email:
            QMessageBox.warning(self,"Datos incompletos","Escribe el nombre y un correo institucional válido.")
            return
        if any(s["email"].lower()==email.lower() for s in self.students):
            QMessageBox.warning(self,"Estudiante existente","Ese correo ya está registrado en la clase actual.")
            return
        self.students.append({"name":name,"email":email,"time":"—","status":"Pendiente"})
        c=self.classes[self.current_class]
        if name not in c["students"]: c["students"].append(name)
        if not any(n==name for n,e in self.all_students): self.all_students.append((name,email))
        self.student_name.clear(); self.student_email.clear()
        self.refresh_students_table(); self.refresh_attendance_table()
        QMessageBox.information(self,"Estudiante añadido","Se añadió al listado local de demostración.")

    def refresh_students_table(self, rows=None):
        if not hasattr(self,"students_table"): return
        shown=rows if rows is not None else self.all_students
        self.students_table.setRowCount(len(shown))
        for r,row in enumerate(shown):
            for col,val in enumerate(row): self.students_table.setItem(r,col,QTableWidgetItem(val))

    def filter_students(self, text):
        term=text.lower().strip()
        self.refresh_students_table([s for s in self.all_students if term in s[0].lower() or term in s[1].lower()])

    def refresh_attendance_table(self, rows=None):
        if not hasattr(self,"attendance_table"): return
        shown=rows if rows is not None else self.students
        self.attendance_table.setRowCount(len(shown))
        colors={"Presente":("#DDF7E8","#18794E"),"Manual":("#DDF7E8","#18794E"),
                "Tarde":("#FCE8E7","#B42318"),"Sin registrar":("#FCE8E7","#B42318"),
                "Pendiente":("#EDF0F5","#596579")}
        for r,s in enumerate(shown):
            values=[s["name"],s["email"],s["time"],s["status"]]
            bg,fg=colors.get(s["status"],("#EDF0F5","#596579"))
            for col,val in enumerate(values):
                item=QTableWidgetItem(val)
                item.setBackground(QColor(bg))
                if col==3:
                    item.setForeground(QColor(fg))
                    item.setFont(QFont("Segoe UI",9,QFont.Bold))
                self.attendance_table.setItem(r,col,item)
        present=sum(s["status"] in ("Presente","Manual") for s in self.students)
        late=sum(s["status"] in ("Tarde","Sin registrar") for s in self.students)
        pending=sum(s["status"]=="Pendiente" for s in self.students)
        self.metric_total.value_label.setText(str(len(self.students)))
        self.metric_present.value_label.setText(str(present))
        self.metric_late.value_label.setText(str(late))
        self.metric_pending.value_label.setText(str(pending))

    def filter_attendance(self,text):
        term=text.lower().strip()
        self.refresh_attendance_table([s for s in self.students if term in s["name"].lower() or term in s["email"].lower()])

    def start_session(self):
        if self.session_active: return
        self.session_active=True
        self.session_label.setText("● Sesión activa · Captura habilitada (simulada)")
        self.session_label.setStyleSheet("color:#18794E;font-weight:700;")
        self.device_status.setText("●  ESP32-CAM habilitado (simulado)")
        self.device_status.setStyleSheet("color:#8DE0B0;font-size:12px;font-weight:700;")
        self.start_btn.setEnabled(False); self.finish_btn.setEnabled(True)
        QMessageBox.information(self,"Asistencia iniciada","La sesión se inició en la interfaz de demostración. La activación real del ESP32-CAM se conectará mediante FastAPI.")

    def finish_session(self):
        if not self.session_active: return
        answer=QMessageBox.question(self,"Finalizar clase","¿Deseas finalizar la sesión de asistencia?",
                                    QMessageBox.Yes|QMessageBox.No,QMessageBox.No)
        if answer!=QMessageBox.Yes: return
        self.session_active=False
        for s in self.students:
            if s["status"]=="Pendiente":
                s["status"]="Sin registrar"
        self.session_label.setText("● Sesión finalizada")
        self.session_label.setStyleSheet("color:#B42318;font-weight:700;")
        self.device_status.setText("●  ESP32-CAM en espera")
        self.device_status.setStyleSheet("color:#F6D98B;font-size:12px;font-weight:700;")
        self.start_btn.setEnabled(True); self.finish_btn.setEnabled(False)
        # Update status styling for the final result
        self.refresh_attendance_table()
        QMessageBox.information(self,"Clase finalizada","La sesión se cerró en modo demostración. Puedes guardar o exportar la lista.")

    def manual_attendance(self):
        row=self.attendance_table.currentRow()
        if row<0:
            QMessageBox.warning(self,"Selecciona un estudiante","Selecciona una fila de la tabla antes de añadir asistencia.")
            return
        email_item=self.attendance_table.item(row,1)
        email=email_item.text() if email_item else ""
        student=next((s for s in self.students if s["email"]==email),None)
        if not student: return
        if student["status"] in ("Presente","Manual","Tarde"):
            QMessageBox.information(self,"Ya tiene registro","Este estudiante ya tiene un registro en la sesión.")
            return
        now=datetime.now().strftime("%H:%M")
        student["time"]=now; student["status"]="Manual"
        self.refresh_attendance_table()
        QMessageBox.information(self,"Asistencia manual",f"Se añadió asistencia manual para {student['name']} a las {now}.")

    def export_attendance(self):
        path,_=QFileDialog.getSaveFileName(self,"Exportar asistencia","asistencia.csv","CSV (*.csv)")
        if not path: return
        try:
            with open(path,"w",newline="",encoding="utf-8-sig") as f:
                writer=csv.writer(f)
                writer.writerow(["Asignatura","Nombre","Correo institucional","Hora de registro","Estado","Origen"])
                for s in self.students:
                    origin="Manual" if s["status"]=="Manual" else "Automático (demostración)"
                    writer.writerow([self.classes[self.current_class]["name"],s["name"],s["email"],s["time"],s["status"],origin])
            QMessageBox.information(self,"Exportación completada",f"Se guardó el CSV en:\n{path}\n\nLa escritura en MySQL se añadirá al conectar FastAPI.")
        except OSError as e:
            QMessageBox.critical(self,"Error al exportar",str(e))

    def refresh_history_table(self):
        if not hasattr(self,"history_table"): return
        self.history_table.setRowCount(1)
        values=[self.classes[self.current_class]["name"],datetime.now().strftime("%d/%m/%Y"),
                str(sum(s["status"] in ("Presente","Manual","Tarde") for s in self.students)),"Demostración"]
        for col,val in enumerate(values): self.history_table.setItem(0,col,QTableWidgetItem(val))


if __name__ == "__main__":
    app=QApplication(sys.argv)
    app.setFont(QFont("Segoe UI",10))
    window=AttendanceApp()
    window.show()
    sys.exit(app.exec())
