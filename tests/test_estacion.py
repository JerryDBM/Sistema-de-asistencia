"""Pruebas de la estación: lectura del QR, respuestas de la API y LED."""
# Simula una cámara de red y permite atenderla sin bloquear las pruebas.
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import pytest

from conftest import foto_con_qr, foto_sin_qr
from estacion import (
    LED_NARANJA, LED_ROJO, LED_VERDE, CameraError, EspCamClient, ScanProcessor,
    clasificar_respuesta, decode_qr, extraer_email, normalizar_url,
)


# ------------------------------------------------------------ lectura QR ---
@pytest.mark.parametrize("escala", [0.35, 0.55, 0.8])
def test_lee_el_correo_de_una_foto(escala):
    """Comprueba que el lector reconoce un correo aunque cambie el tamaño del QR."""
    jpeg = foto_con_qr("ana.martinez@utb.edu.co", escala_qr=escala)
    assert decode_qr(jpeg) == ["ana.martinez@utb.edu.co"]


def test_foto_en_baja_resolucion_sin_psram():
    """Comprueba que se puede leer un QR en una imagen pequeña."""
    jpeg = foto_con_qr("carlos.perez@utb.edu.co", tamano=(320, 240), escala_qr=0.8)
    assert decode_qr(jpeg) == ["carlos.perez@utb.edu.co"]


def test_foto_sin_qr_no_devuelve_nada():
    """Confirma que una foto vacía o dañada no produce un correo falso."""
    assert decode_qr(foto_sin_qr()) == []
    assert decode_qr(b"esto no es un jpeg") == []


@pytest.mark.parametrize("texto, esperado", [
    ("Ana.Martinez@UTB.edu.co", "ana.martinez@utb.edu.co"),
    ("  mailto:laura.gomez@utb.edu.co ", "laura.gomez@utb.edu.co"),
    ("https://utb.edu.co", None),
    ("hola", None),
])
def test_extraer_email(texto, esperado):
    """Verifica que solo se acepten correos y que se limpien espacios y mayúsculas."""
    assert extraer_email(texto) == esperado


@pytest.mark.parametrize("entrada, salida", [
    ("192.168.1.50", "http://192.168.1.50"),
    ("http://192.168.1.50/", "http://192.168.1.50"),
    ("aulacheck-cam.local", "http://aulacheck-cam.local"),
    ("", ""),
])
def test_normalizar_url(entrada, salida):
    """Comprueba que las direcciones de cámara se completen y limpien correctamente."""
    assert normalizar_url(entrada) == salida


# ------------------------------------------------- respuesta API -> LED ---
def test_clasificacion_de_respuestas():
    """Comprueba el título y color que corresponden a las respuestas de la API."""
    assert clasificar_respuesta("a@b.co", 201, {"status": "present", "student_name": "Ana"}).led == LED_VERDE
    assert clasificar_respuesta("a@b.co", 201, {"status": "tardy", "student_name": "Ana"}).led == LED_ROJO
    duplicado = clasificar_respuesta("a@b.co", 409, {"detail": "DUPLICATE: el estudiante ya tiene un registro"})
    assert (duplicado.led, duplicado.titulo) == (LED_NARANJA, "Ya registrado")
    assert clasificar_respuesta("a@b.co", 409, {"detail": "La sesión ya está finalizada."}).titulo == "Sesión cerrada"
    assert clasificar_respuesta("a@b.co", 400, {"detail": "no vinculado"}).titulo == "No matriculado"
    assert clasificar_respuesta("a@b.co", 404, {"detail": "no existe"}).titulo == "Correo no registrado"
    assert clasificar_respuesta("a@b.co", 500, "error").led == LED_ROJO


# -------------------------------------- flujo completo contra la API real ---
class Reloj:
    """Reloj controlable para simular el paso del tiempo sin esperar de verdad."""
    def __init__(self):
        """Empieza el reloj simulado en un valor conocido."""
        self.t = 1000.0

    def __call__(self):
        """Devuelve el tiempo actual que las pruebas pueden adelantar manualmente."""
        return self.t


def test_flujo_completo_verde_naranja_y_espera(client, sesion_a_tiempo):
    """Prueba lectura puntual, pausa anti repetición y detección de duplicado."""
    reloj = Reloj()
    proc = ScanProcessor("", sesion_a_tiempo, cooldown_s=6, http=client, clock=reloj)
    foto = foto_con_qr("ana.martinez@utb.edu.co")

    primero = proc.process_frame(foto)
    assert (primero.led, primero.titulo, primero.estudiante) == (LED_VERDE, "Presente", "Ana Martinez")

    # Mismo QR frente a la cámara 1 s después: se ignora (no repite ni pone naranja).
    reloj.t += 1
    assert proc.process_frame(foto) is None

    # Vuelve a mostrarlo pasado el tiempo de espera: ya estaba registrado -> naranja.
    reloj.t += 10
    segundo = proc.process_frame(foto)
    assert (segundo.led, segundo.titulo) == (LED_NARANJA, "Ya registrado")

    registros = client.get(f"/sessions/{sesion_a_tiempo}/attendance").json()
    assert [(r["student_email"], r["status"], r["source"]) for r in registros] == [
        ("ana.martinez@utb.edu.co", "present", "qr")
    ]


def test_flujo_rojos(client, sesion_a_tiempo, sesion_tarde):
    """Comprueba los avisos de rechazo, tardanza y sesión que ya se cerró."""
    proc = ScanProcessor("", sesion_a_tiempo, http=client, clock=Reloj())
    assert proc.process_frame(foto_con_qr("laura.gomez@utb.edu.co")).titulo == "No matriculado"
    assert proc.process_frame(foto_con_qr("nadie@utb.edu.co")).titulo == "Correo no registrado"
    assert proc.process_frame(foto_con_qr("https://example.com")).titulo == "QR no válido"
    assert proc.process_frame(foto_sin_qr()) is None

    tarde = ScanProcessor("", sesion_tarde, http=client, clock=Reloj())
    resultado = tarde.process_frame(foto_con_qr("laura.gomez@utb.edu.co"))
    assert (resultado.led, resultado.titulo) == (LED_ROJO, "Fuera de tolerancia")

    client.post(f"/sessions/{sesion_a_tiempo}/finish")
    proc2 = ScanProcessor("", sesion_a_tiempo, http=client, clock=Reloj())
    assert proc2.process_frame(foto_con_qr("carlos.perez@utb.edu.co")).titulo == "Sesión cerrada"


def test_api_caida_da_rojo_sin_romper():
    """Asegura que una API inaccesible produzca un mensaje y no detenga la estación."""
    proc = ScanProcessor("http://127.0.0.1:9", 1, clock=Reloj())
    resultado = proc.process_frame(foto_con_qr("ana.martinez@utb.edu.co"))
    assert (resultado.led, resultado.titulo) == (LED_ROJO, "Sin conexión con la API")


# ------------------------------------------ ESP32-CAM simulada por HTTP ---
class CamaraFalsa(BaseHTTPRequestHandler):
    """Imita las rutas del firmware: /capture, /status, /led, /flash."""

    foto = b""
    leds: list = []

    def log_message(self, *args):
        """Silencia mensajes de red para que no llenen la salida de las pruebas."""
        pass

    def _responder(self, codigo, tipo, cuerpo):
        """Envía una respuesta HTTP simulada con código, formato y contenido."""
        self.send_response(codigo)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(cuerpo)))
        self.end_headers()
        self.wfile.write(cuerpo)

    def do_GET(self):
        """Responde a las rutas que normalmente ofrece el firmware de la cámara."""
        url = urlparse(self.path)
        q = parse_qs(url.query)
        if url.path == "/capture":
            self._responder(200, "image/jpeg", self.foto)
        elif url.path == "/status":
            self._responder(200, "application/json", b'{"camera":true,"ip":"127.0.0.1","rssi":-50}')
        elif url.path == "/led":
            CamaraFalsa.leds.append(q.get("state", [""])[0])
            self._responder(200, "application/json", b'{"ok":true}')
        else:
            self._responder(404, "application/json", b"{}")


@pytest.fixture()
def camara_falsa():
    """Levanta un servidor de cámara de prueba y lo apaga al finalizar cada uso."""
    CamaraFalsa.leds = []
    servidor = ThreadingHTTPServer(("127.0.0.1", 0), CamaraFalsa)
    hilo = threading.Thread(target=servidor.serve_forever, daemon=True)
    hilo.start()
    yield f"127.0.0.1:{servidor.server_port}"
    servidor.shutdown()


def test_cliente_de_la_camara(camara_falsa):
    """Comprueba estado, foto y luz de la cámara falsa desde el cliente real."""
    CamaraFalsa.foto = foto_con_qr("ana.martinez@utb.edu.co")
    cam = EspCamClient(camara_falsa)
    assert cam.status()["camera"] is True
    assert decode_qr(cam.capture()) == ["ana.martinez@utb.edu.co"]
    assert cam.led(LED_VERDE) is True
    assert CamaraFalsa.leds == ["green"]


def test_camara_que_no_envia_jpeg(camara_falsa):
    """Comprueba que una respuesta que no es foto se reporte como error."""
    CamaraFalsa.foto = b"<html>otra cosa</html>"
    with pytest.raises(CameraError, match="no envió una foto JPEG"):
        EspCamClient(camara_falsa).capture()


def test_camara_apagada():
    """Comprueba que el cliente detecte una cámara apagada y pueda fallar sin caerse."""
    cam = EspCamClient("127.0.0.1:9", timeout=1)
    with pytest.raises(CameraError, match="No hay conexión"):
        cam.capture()
    assert cam.led(LED_VERDE) is False
