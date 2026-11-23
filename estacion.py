"""Estación de lectura ESP32-CAM de AulaCheck.

La placa (firmware ``firmware/aulacheck_cam``) solo toma fotos y enciende LED.
Este módulo hace el resto en el computador del docente:

1. Pide una foto a la ESP32-CAM por WiFi (``GET /capture``).
2. Busca un QR en la foto con OpenCV y obtiene el correo del estudiante.
3. Envía el correo a la API: ``POST /sessions/{id}/attendance/scan``.
4. Traduce la respuesta de la API a un resultado (verde, rojo o naranja) y se
   lo indica a la placa (``GET /led?state=...``).

No depende de Qt: la interfaz PySide6 lo usa desde un hilo aparte, y también
se puede probar sin interfaz.
"""
from __future__ import annotations

# Herramientas para validar correos, medir tiempos y guardar el resultado de cada lectura.
import re
import time
from dataclasses import dataclass

import cv2
import numpy as np
import requests

# Nombres de las señales que la estación puede pedirle a la cámara.
LED_VERDE = "green"
LED_ROJO = "red"
LED_NARANJA = "orange"
LED_APAGADO = "off"

# Regla sencilla para reconocer textos que parecen una dirección de correo.
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@dataclass
class ScanResult:
    """Resultado de una lectura, listo para mostrar en la interfaz y en los LED."""

    # Correo o texto encontrado en el QR.
    email: str
    # Color que indica el resultado al docente o al estudiante.
    led: str            # green | red | orange
    # Mensaje breve que resume lo ocurrido.
    titulo: str         # texto corto: «Presente», «Ya registrado», ...
    # Motivo más detallado que se puede mostrar en pantalla.
    detalle: str        # explicación para el docente
    # Nombre real, si la API lo devolvió.
    estudiante: str | None = None


class CameraError(RuntimeError):
    """La ESP32-CAM no respondió o devolvió algo que no es una foto."""


def normalizar_url(url: str) -> str:
    """Acepta «192.168.1.50», «http://192.168.1.50/» o «aulacheck-cam.local»."""
    # Quita espacios y permite recibir una dirección vacía sin producir un error.
    # Si no se recibió una dirección, usa texto vacío; luego quita espacios sobrantes.
    url = (url or "").strip()
    # Agrega el protocolo web si la dirección no lo incluye.
    if url and not url.lower().startswith(("http://", "https://")):
        url = "http://" + url
    # Quita las barras finales para añadir rutas sin repetir barras.
    return url.rstrip("/")


class EspCamClient:
    """Habla con el firmware de la ESP32-CAM por HTTP."""

    def __init__(self, base_url: str, timeout: float = 4.0):
        """Guarda la dirección de la cámara y prepara una conexión reutilizable."""
        # Guarda la dirección de la cámara después de ordenarla.
        self.base_url = normalizar_url(base_url)
        # Establece cuántos segundos se espera una respuesta antes de rendirse.
        self.timeout = timeout
        # Crea una conexión HTTP que se puede reutilizar en varias consultas.
        self.http = requests.Session()

    def _get(self, path: str, **params) -> requests.Response:
        """Hace una consulta HTTP a la cámara y traduce fallos de red a mensajes claros."""
        # No se puede consultar la cámara si falta su dirección.
        if not self.base_url:
            raise CameraError("No se ha escrito la dirección de la ESP32-CAM.")
        try:
            # Envía una solicitud a la ruta indicada y espera solo el tiempo establecido.
            response = self.http.get(f"{self.base_url}{path}", params=params or None, timeout=self.timeout)
        except requests.RequestException as exc:
            # Convierte el fallo técnico de red en una explicación útil para el docente.
            raise CameraError(
                f"No hay conexión con la ESP32-CAM en {self.base_url}. "
                "Revise que esté encendida, en la misma red WiFi y que la IP sea la correcta."
            ) from exc
        return response

    def capture(self) -> bytes:
        """Solicita una foto y comprueba que la respuesta realmente sea una imagen JPEG."""
        # Solicita que la cámara tome y devuelva una fotografía.
        response = self._get("/capture")
        # El código 503 significa que la cámara respondió, pero no pudo iniciar su sensor.
        if response.status_code == 503:
            raise CameraError("La ESP32-CAM está en la red, pero su cámara no inició (revise el cable plano y pulse RST).")
        # Si la cámara informa un error, no se puede usar su respuesta como foto.
        if not response.ok:
            raise CameraError(f"La ESP32-CAM respondió con error HTTP {response.status_code}.")
        # Comprueba que los datos recibidos comiencen como una imagen JPEG.
        if not response.content.startswith(b"\xff\xd8"):
            raise CameraError("La ESP32-CAM respondió, pero no envió una foto JPEG. ¿Tiene cargado el firmware de AulaCheck?")
        # Devuelve los datos de la fotografía para que se puedan analizar.
        return response.content

    def status(self) -> dict:
        """Pide el estado de la cámara y devuelve los datos recibidos en formato JSON."""
        # Solicita a la cámara información sobre su estado.
        response = self._get("/status")
        # Comprueba que la cámara haya contestado correctamente.
        if not response.ok:
            raise CameraError(f"La ESP32-CAM respondió con error HTTP {response.status_code}.")
        try:
            # Convierte el texto JSON de la respuesta en datos que Python puede manejar.
            return response.json()
        except ValueError as exc:
            # Avisa si la respuesta no tiene el formato esperado de la cámara AulaCheck.
            raise CameraError("La dirección responde, pero no parece ser la ESP32-CAM de AulaCheck.") from exc

    def led(self, state: str) -> bool:
        """Enciende un LED. Devuelve False si no se pudo (no detiene la lectura)."""
        try:
            # Pide a la cámara que encienda el LED del color indicado.
            return self._get("/led", state=state).ok
        except CameraError:
            # Indica el fallo sin interrumpir la lectura de códigos QR.
            return False

    def flash(self, on: bool) -> bool:
        """Enciende o apaga la luz auxiliar; informa si la cámara aceptó la orden."""
        try:
            # Envía 1 para encender la luz auxiliar o 0 para apagarla.
            return self._get("/flash", on=1 if on else 0).ok
        except CameraError:
            # Informa que no se pudo controlar la luz, pero permite continuar.
            return False


# ----------------------------------------------------------- lectura de QR ---
_detector = cv2.QRCodeDetector()


def _decodificar(imagen) -> list[str]:
    """Busca uno o varios códigos QR en una imagen y devuelve los textos encontrados."""
    # Aquí se guardarán los textos encontrados dentro de los códigos QR.
    textos: list[str] = []
    try:
        # Primero intenta encontrar y leer varios códigos QR en la imagen.
        ok, decodificados, _puntos, _ = _detector.detectAndDecodeMulti(imagen)
        # Guarda los resultados solo si OpenCV confirmó que pudo detectarlos.
        if ok:
            textos = [t for t in decodificados if t]
    except cv2.error:
        pass
    if not textos:
        try:
            # Si no leyó varios, intenta leer un solo código QR.
            texto, _puntos, _ = _detector.detectAndDecode(imagen)
            if texto:
                textos = [texto]
        except cv2.error:
            # Si OpenCV falla, devuelve lo que haya encontrado sin cerrar el programa.
            pass
    # Entrega todos los textos que pudo leer; la lista puede estar vacía.
    return textos


def decode_qr(jpeg: bytes) -> list[str]:
    """Devuelve el texto de los QR encontrados en una foto JPEG (puede ser vacío)."""
    # Convierte los bytes de la foto a una matriz que OpenCV puede analizar.
    # Interpreta los bytes de la foto como datos numéricos de una imagen.
    datos = np.frombuffer(jpeg, dtype=np.uint8)
    # Abre la foto JPEG y la convierte a tonos grises para analizarla.
    imagen = cv2.imdecode(datos, cv2.IMREAD_GRAYSCALE)
    # Si no se pudo abrir la foto, no hay QR que buscar.
    if imagen is None:
        return []
    # 1) La foto tal cual. 2) Con más contraste: ayuda con pantallas de celular
    # con brillo bajo o reflejos. 3) Ampliada: ayuda si el QR quedó pequeño.
    # Prepara la imagen original y otra con más contraste para probar ambas.
    intentos = [imagen, cv2.equalizeHist(imagen)]
    # También prepara una copia ampliada cuando la foto es pequeña.
    if max(imagen.shape) < 1000:
        intentos.append(cv2.resize(imagen, None, fx=1.6, fy=1.6, interpolation=cv2.INTER_CUBIC))
    # Prueba las versiones de la imagen hasta que encuentre algún QR legible.
    for candidato in intentos:
        # Busca códigos QR en esta versión de la foto.
        textos = _decodificar(candidato)
        if textos:
            # Prepara una lista limpia, sin espacios ni códigos repetidos.
            unicos = []
            for t in textos:
                t = t.strip()
                if t and t not in unicos:
                    unicos.append(t)
                # Al encontrar resultados, los devuelve sin seguir probando otras imágenes.
            return unicos
            # Ninguna versión permitió leer un código QR.
    return []


def extraer_email(texto: str) -> str | None:
    """El QR de la app Flutter contiene solo el correo institucional."""
    # Limpia el texto y acepta también el formato de enlace `mailto:`.
    # Quita espacios externos; si no había texto, usa una cadena vacía.
    texto = (texto or "").strip()
    # Retira el prefijo mailto: que puede aparecer en enlaces de correo.
    if texto.lower().startswith("mailto:"):
        texto = texto[7:]
    # Deja el correo en minúsculas para compararlo siempre de la misma manera.
    texto = texto.strip().lower()
    # Devuelve el texto solo si parece un correo; si no, indica que no es válido.
    return texto if EMAIL_RE.match(texto) else None


# ------------------------------------------------- respuesta de la API -> LED ---
def clasificar_respuesta(email: str, status_code: int, cuerpo) -> ScanResult:
    """Convierte la respuesta de POST /sessions/{id}/attendance/scan en un resultado."""
    # Extrae el mensaje de error de la API cuando está disponible.
    # Comienza sin detalle de error, porque la API quizá no envíe ninguno.
    detalle_api = ""
    # Si la respuesta es un diccionario, busca en él el mensaje llamado detail.
    if isinstance(cuerpo, dict):
        detalle_api = str(cuerpo.get("detail", ""))
    # Si llegó otro tipo de respuesta con contenido, lo convierte en texto.
    elif cuerpo:
        detalle_api = str(cuerpo)

    # Los códigos 200 y 201 significan que la API aceptó la solicitud.
    if status_code in (200, 201) and isinstance(cuerpo, dict):
        # Lee el nombre y el estado de asistencia enviados por la API.
        nombre = cuerpo.get("student_name")
        estado = cuerpo.get("status")
        # Una asistencia a tiempo se informa con verde.
        if estado == "present":
            return ScanResult(email, LED_VERDE, "Presente", "Asistencia registrada a tiempo.", nombre)
        # Una llegada tarde se informa con rojo y una explicación.
        if estado == "tardy":
            return ScanResult(email, LED_ROJO, "Fuera de tolerancia",
                              "Llegó después del tiempo de tolerancia; queda como «Tarde».", nombre)
        # Cualquier otro estado aceptado se presenta como un registro correcto.
        return ScanResult(email, LED_VERDE, "Registrado", f"Estado: {estado}.", nombre)
    # El mensaje DUPLICATE indica que la asistencia ya se había registrado.
    if status_code == 409 and detalle_api.startswith("DUPLICATE"):
        return ScanResult(email, LED_NARANJA, "Ya registrado",
                          "El estudiante ya tenía asistencia en esta sesión; no se creó otro registro.")
    # Otro conflicto indica que no se pudo registrar, normalmente porque cerraron la sesión.
    if status_code == 409:
        return ScanResult(email, LED_ROJO, "Sesión cerrada", detalle_api or "La sesión ya está finalizada.")
    # El código 400 indica que el estudiante no pertenece a la clase.
    if status_code == 400:
        return ScanResult(email, LED_ROJO, "No matriculado", detalle_api or "El estudiante no pertenece a esta clase.")
    # El código 404 indica que no se encontró el correo.
    if status_code == 404:
        return ScanResult(email, LED_ROJO, "Correo no registrado", detalle_api or "El correo no existe en la base de datos.")
    # Para cualquier otro problema, muestra el código recibido y el detalle disponible.
    return ScanResult(email, LED_ROJO, "Error", f"La API respondió HTTP {status_code}. {detalle_api}".strip())


class ScanProcessor:
    """Procesa fotos de una sesión: lee el QR, consulta la API y evita repeticiones.

    ``http`` es cualquier objeto con ``post(url, json=..., timeout=...)``: un
    ``requests.Session`` en uso normal o el cliente de pruebas de FastAPI.
    """

    def __init__(self, api_base: str, session_id: int, cooldown_s: float = 6.0,
                 http=None, clock=time.monotonic):
        """Prepara la comunicación con la API y la memoria para evitar lecturas repetidas."""
        # Guarda la dirección del servidor quitando una barra final si existe.
        self.api_base = (api_base or "").rstrip("/")
        # Guarda qué sesión recibirá las asistencias.
        self.session_id = session_id
        # Define cuántos segundos se ignora una lectura repetida.
        self.cooldown_s = cooldown_s
        # Usa el cliente HTTP recibido o crea uno nuevo para hablar con la API.
        self.http = http or requests.Session()
        # Guarda el reloj que se usará para medir el tiempo entre lecturas.
        self.clock = clock
        # Recuerda cuándo se leyó por última vez cada correo o texto QR.
        self._ultimas: dict[str, float] = {}

    def _en_espera(self, clave: str) -> bool:
        """True si ese QR ya se procesó hace menos de ``cooldown_s`` segundos.

        Así, mientras el estudiante sigue frente a la cámara, su QR no se envía
        una y otra vez (ni se enciende el naranja justo después del verde).
        """
        # Averigua el momento actual.
        ahora = self.clock()
        # Busca el momento en que se procesó esta clave la vez anterior.
        anterior = self._ultimas.get(clave)
        # Si pasó poco tiempo, señala que esta lectura debe ignorarse.
        if anterior is not None and ahora - anterior < self.cooldown_s:
            return True
        # Si ya se puede procesar, guarda el momento actual como nueva referencia.
        self._ultimas[clave] = ahora
        # False significa que la lectura no está repetida y puede continuar.
        return False

    def enviar(self, email: str) -> ScanResult:
        """Envía el correo a la API para que registre asistencia y traduce la respuesta."""
        # Construye la dirección web para registrar asistencia en esta sesión.
        url = f"{self.api_base}/sessions/{self.session_id}/attendance/scan"
        try:
            # Envía el correo a la API y espera como máximo cinco segundos.
            response = self.http.post(url, json={"email": email}, timeout=5)
        except requests.RequestException:
            # Si no hay conexión, devuelve un aviso en lugar de detener el programa.
            return ScanResult(email, LED_ROJO, "Sin conexión con la API",
                              "No se pudo contactar a FastAPI. Revise que el backend siga ejecutándose.")
        try:
            # Intenta leer la respuesta de la API como datos JSON.
            cuerpo = response.json()
        except ValueError:
            # Si la respuesta no es JSON, guarda el texto recibido.
            cuerpo = response.text
        # Decide el mensaje y el color según la respuesta de la API.
        return clasificar_respuesta(email, response.status_code, cuerpo)

    def process_frame(self, jpeg: bytes) -> ScanResult | None:
        """Devuelve un resultado si la foto tenía un QR nuevo; si no, None."""
        # Busca QR en la foto; sin resultados no hay nada que registrar.
        # Examina la fotografía y obtiene el texto de cada código QR legible.
        textos = decode_qr(jpeg)
        # Si no encontró ningún código, no hay nada que enviar a la API.
        if not textos:
            return None
        # Conserva el primer texto por si hace falta avisar que el QR no es válido.
        texto = textos[0]
        # Busca entre los textos el primero que tenga formato de correo electrónico.
        email = next((e for e in (extraer_email(t) for t in textos) if e), None)
        # Si ninguno era un correo, prepara un aviso de código no válido.
        if email is None:
            # Evita repetir el mismo aviso mientras el código siga delante de la cámara.
            if self._en_espera("texto:" + texto):
                return None
            # Limita el texto mostrado para que no ocupe demasiado espacio.
            return ScanResult(texto[:60], LED_ROJO, "QR no válido",
                              "El QR no contiene un correo institucional. Use el QR de la app AulaCheck.")
        # Ignora el correo si ya se procesó hace poco.
        if self._en_espera(email):
            return None
        # El correo es válido y nuevo: pide a la API que registre la asistencia.
        return self.enviar(email)
