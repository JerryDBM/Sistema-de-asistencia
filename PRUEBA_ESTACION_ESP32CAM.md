# AulaCheck · Cómo probar la estación ESP32-CAM

Esta guía lleva paso a paso desde descomprimir el proyecto hasta registrar asistencia con un QR frente a la cámara. Está dividida en fases: si una falla, deténgase ahí y revise la sección **Si algo falla** al final antes de seguir.

| Fase | Qué se comprueba | Necesita la placa |
|---|---|---|
| 0 | Proyecto, Python y MySQL listos | No |
| 1 | El código funciona en este PC (pruebas automáticas) | No |
| 2 | La placa toma fotos y se conecta al WiFi | Sí |
| 3 | La interfaz del docente ve la cámara | Sí |
| 4 | Clase de prueba a la hora actual | No |
| 5 | Prueba completa con QR y LED | Sí |

---

## Fase 0 · Preparar el proyecto (una sola vez)

1. Descomprima el ZIP, por ejemplo en `C:\Users\Nestor\Downloads\`. Queda la carpeta `sistema-de-asistencia`.

2. Abra PowerShell **dentro de esa carpeta** (la que tiene `main.py`) y cree el entorno con Python 3.12:

   ```powershell
   cd C:\Users\Nestor\Downloads\sistema-de-asistencia
   py -3.12 -m venv .venv
   .\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
   ```

   `requirements-dev.txt` instala todo lo del proyecto más lo necesario para las pruebas.

3. Copie la configuración y escriba el usuario y la clave de MySQL:

   ```powershell
   Copy-Item .env.example .env
   notepad .env
   ```

   Complete `DB_USER` y `DB_PASSWORD`, guarde y cierre el Bloc de notas.

4. Si la base de datos `aulacheck` no existe, créela en MySQL Workbench:

   ```sql
   CREATE DATABASE aulacheck CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
   ```

5. Cargue los estudiantes de prueba:

   ```powershell
   .\.venv\Scripts\python.exe seed.py
   ```

   ✅ Debe decir: `Datos de prueba listos. Clase de ejemplo: NRC 10001.`

---

## Fase 1 · Pruebas automáticas (sin placa)

Comprueban que el código funciona en este PC antes de tocar el hardware. Usan una base de datos temporal y una cámara simulada, así que no necesitan MySQL ni la ESP32-CAM.

```powershell
.\.venv\Scripts\python.exe -m pytest
```

✅ Debe terminar con **`20 passed`**.

---

## Fase 2 · Cargar el firmware y probar la placa sola

### 2.1 · Instalar Arduino IDE (una sola vez)

1. Descargue **Arduino IDE 2.x** desde <https://www.arduino.cc/en/software> (versión **Windows · Win 10 and newer, 64 bits**).
2. Instálelo con las opciones por defecto. Si Windows pregunta por instalar **drivers** (controladores USB), acepte.
3. Ábralo una vez y espere a que termine de preparar sus herramientas (abajo a la derecha se ven mensajes de descarga).

> Los nombres de los menús en esta guía están en **inglés**. Si su Arduino IDE está en español: **Tools** = *Herramientas*, **Board** = *Placa*, **Port** = *Puerto*, **Boards Manager** = *Gestor de tarjetas*, **Upload** = *Subir*, **File › Preferences** = *Archivo › Preferencias*.

### 2.2 · Instalar el paquete de placas ESP32 (una sola vez)

Sin este paquete, el Arduino IDE no sabe compilar para la ESP32-CAM y aparece el error `esp_camera.h: No such file or directory`.

1. Vaya a **Tools › Board › Boards Manager…** (o pulse **Ctrl+Shift+B**, o el segundo ícono de la barra izquierda).
2. En el buscador escriba `esp32`.
3. Busque **esp32 by Espressif Systems**. No confundir con *Arduino ESP32 Boards*, que es otro paquete.
4. Pulse **INSTALL** y espere a que la consola de abajo diga que terminó. Es una descarga grande, de varios minutos.

**Si no aparece «esp32 by Espressif Systems»:**

1. Vaya a **File › Preferences…**.
2. En **Additional boards manager URLs** pegue:

   ```text
   https://espressif.github.io/arduino-esp32/package_esp32_index.json
   ```

3. Pulse **OK** y repita la búsqueda en el Boards Manager.

**Si la instalación falla con un error de descarga** (por ejemplo `Failed to install platform ... EOF`):

- Pulse **INSTALL** otra vez; muchas veces es un corte puntual.
- Cambie de red (por ejemplo, a los datos del celular); algunas redes, como la de la universidad, cortan estas descargas.
- En la lista de versiones junto al botón INSTALL, elija **2.0.17** e instálela. Es más liviana, y el firmware de AulaCheck compila con ella.

### 2.3 · Conectar la placa

1. Ponga la ESP32-CAM sobre la base **ESP32-CAM-MB**, con la cámara del mismo lado que el conector USB y todos los pines bien insertados.
2. Conecte la base al PC con un **cable USB de datos**.
3. Compruebe el puerto en el **Administrador de dispositivos** de Windows, en **Puertos (COM y LPT)**: debe aparecer algo como **USB-SERIAL CH340 (COM3)**. Anote el número de COM.
   - Si no aparece, instale el **driver CH340** y vuelva a conectar la placa.
4. Cierre cualquier programa que pueda estar usando ese puerto: Thonny, PuTTY, otro Serial Monitor o pestañas del navegador con herramientas de grabación.

### 2.4 · Configurar y subir el firmware

1. En Arduino IDE, abra **File › Open…** y elija `firmware\aulacheck_cam\aulacheck_cam.ino` dentro de la carpeta del proyecto.

2. Al inicio del archivo, en la sección **CONFIGURACIÓN**, cambie estas dos líneas por los datos de su red:

   ```cpp
   const char *WIFI_SSID = "NOMBRE_DE_LA_RED";
   const char *WIFI_PASSWORD = "CLAVE_DE_LA_RED";
   ```

   > **Importante:** la red debe ser de **2,4 GHz** y con clave normal. Las redes con página de inicio de sesión o usuario institucional (como la WiFi de la universidad) no funcionan.
   > **Recomendado:** active el **punto de acceso del celular** y conecte también el **PC** a esa misma red. La placa y el PC deben estar siempre en la misma red.

   Opcional, en la misma sección:
   - `LED_VERDE_PIN`, `LED_ROJO_PIN`, `LED_NARANJA_PIN`: los pines de los LED (por defecto 13, 14 y 15).
   - `BUZZER_PIN`: `-1` sin buzzer; `2` para usarlo (conectado mediante un transistor).

3. Seleccione la placa y el puerto. Hay dos formas:

   **Opción A · Selector de arriba (más fácil)**
   1. Haga clic en la lista desplegable de la barra superior (dice **Select Board** o el nombre de otra placa).
   2. Elija **Select other board and port…**.
   3. En **BOARDS**, escriba `AI Thinker` y seleccione **AI Thinker ESP32-CAM**.
   4. En **PORTS**, seleccione el COM anotado (por ejemplo **COM3**).
   5. Pulse **OK**.

   **Opción B · Menú**
   - **Tools › Board › esp32 › AI Thinker ESP32-CAM** (la lista es larga y está en orden alfabético).
   - **Tools › Port** › el COM anotado.

   ✅ Arriba debe quedar escrito **AI Thinker ESP32-CAM**. Si dice *Arduino Uno* u otra placa, la compilación fallará.

4. Pulse **Upload** (la flecha →). En la consola de abajo verá, en orden:
   - `Compiling sketch...`: la primera vez tarda uno o dos minutos.
   - `Connecting....`
   - `Writing at 0x... (10 %)`, `(20 %)`… hasta `(100 %)`.
   - `Hard resetting via RTS pin...` o **Done uploading**: terminó.

   Si se queda en `Connecting....` o sale `Failed to connect to ESP32`: mantenga **IO0** presionado (botón izquierdo de la base), pulse y suelte **RST** (botón derecho) y suelte IO0. Luego pulse **Upload** de nuevo.

### 2.5 · Ver la dirección IP de la placa

1. Abra **Tools › Serial Monitor**.
2. Abajo a la derecha, ponga la velocidad en **115200 baud**.
3. Pulse **RST** en la base. Debe aparecer algo como:

   ```text
   AulaCheck · Estación ESP32-CAM
   Cámara lista (640x480, PSRAM).
   Conectando a la red "MiCelular"....
   WiFi conectado.
     Dirección para la interfaz: http://192.168.43.120
   ```

   **Anote esa dirección.** Puede cambiar si cambia de red.

   Al arrancar, los tres LED se encienden un instante como saludo. Si sale *«No se pudo conectar al WiFi»*, revise el nombre y la clave, y que la red sea de 2,4 GHz. Después súbalo de nuevo.

4. **Cierre el Serial Monitor.**

### 2.6 · Probar la placa en el navegador

1. En el navegador del PC (conectado a la misma red que la placa), abra la dirección anotada, por ejemplo `http://192.168.43.120`.

   ✅ Debe aparecer la página **«AulaCheck · Estación ESP32-CAM»** con la cámara en vivo. Si ya conectó los LED, pruebe los botones **LED verde**, **LED rojo**, **LED naranja** y **Probar los 3**.

---

## Fase 3 · Arrancar la API y la interfaz

Se necesitan **dos ventanas de PowerShell**, las dos en la carpeta `sistema-de-asistencia`.

### Ventana 1 · API (dejarla abierta)

```powershell
.\.venv\Scripts\python.exe -m uvicorn main:app --reload
```

Compruebe en el navegador que `http://127.0.0.1:8000/health` muestra `"status":"ok"`.

### Ventana 2 · Interfaz del docente

```powershell
.\.venv\Scripts\python.exe interfaz.py
```

### Conectar la cámara en la interfaz

En el panel derecho **ESTACIÓN ESP32-CAM**:

1. Escriba la dirección de la placa (por ejemplo `192.168.43.120`).
2. Pulse **Probar**.

✅ Debe aparecer una foto en el recuadro y el texto **«Cámara lista · señal -XX dBm»**. La dirección queda guardada para la próxima vez.

Botones del panel:

| Botón | Qué hace |
|---|---|
| **Probar** | Comprueba la conexión y muestra una foto |
| **Probar LED** | Enciende los tres LED uno por uno |
| **Flash** | Enciende el LED blanco de la placa (útil con poca luz; en pantallas de celular puede causar reflejos) |

---

## Fase 4 · Crear una clase para probar el verde

La clase del `seed.py` (NRC 10001) empieza a las **8:00 con 10 minutos de tolerancia**. Si prueba a otra hora, todos saldrán en **rojo («Fuera de tolerancia»)**. Eso es correcto según las reglas, pero no permite ver el verde. Por eso hay que crear una clase que empiece ahora:

1. En el menú izquierdo, vaya a **Gestión de clases**.
2. Escriba un nombre (por ejemplo `Prueba estación`), ponga como **hora de inicio la hora actual** y una tolerancia de **15 minutos**.
3. Pulse **Crear clase y generar NRC**.
4. Con esa clase seleccionada, añada estudiantes con **＋ Añadir por correo**:
   - `ana.martinez@utb.edu.co`
   - `carlos.perez@utb.edu.co`
5. Vuelva a **Panel de asistencia** y elija la clase nueva en **Asignatura / NRC**.

---

## Fase 5 · Prueba completa con QR

### Conseguir el QR

Elija una opción:

- **Con la app Flutter:** ábrala, escriba `ana.martinez@utb.edu.co` y muestra su QR.
- **Sin la app (más rápido):** en cualquier generador de QR de internet, cree un QR de **texto** con `ana.martinez@utb.edu.co` y ábralo en el celular.

### La prueba

1. Pulse **▶ Iniciar asistencia**. Debe decir *«La estación ESP32-CAM comenzó a leer los QR»* y el recuadro muestra la cámara en vivo.
2. Ponga el celular con el QR a **15–30 cm** de la cámara, con el **brillo de la pantalla alto** y sin reflejos. Fíjese en el recuadro: el QR debe verse completo.
3. Haga estas pruebas en orden:

| # | Qué mostrar a la cámara | Resultado esperado |
|---|---|---|
| 1 | QR de `ana.martinez@utb.edu.co` | 🟢 **Verde** · «Presente» en *Última lectura*; Ana aparece en la tabla |
| 2 | Retire el celular, **espere 7 segundos** y muestre otra vez el QR de Ana | 🟠 **Naranja** · «Ya registrado» (no se crea otro registro) |
| 3 | QR de `laura.gomez@utb.edu.co` (no está en esta clase) | 🔴 **Rojo** · «No matriculado» |
| 4 | QR de `nadie@utb.edu.co` | 🔴 **Rojo** · «Correo no registrado» |
| 5 | QR con cualquier texto que no sea un correo | 🔴 **Rojo** · «QR no válido» |
| 6 | Pulse **■ Finalizar clase** | La cámara se detiene, los LED se apagan y Carlos queda **Ausente** |

> **¿Por qué esperar 7 segundos en la prueba 2?** Si el mismo QR sigue frente a la cámara, la estación lo ignora durante 6 segundos. Así no registra dos veces al mismo estudiante ni enciende el naranja justo después del verde.

### Prueba extra · fuera de tolerancia

1. Elija la clase **NRC 10001** (la de las 8:00).
2. Pulse **▶ Iniciar asistencia** y muestre el QR de `carlos.perez@utb.edu.co`.

✅ Debe salir 🔴 **rojo** con «Fuera de tolerancia», y en la tabla aparece como **Tarde**.

---

## Qué significa cada LED

| LED | Cuándo se enciende |
|---|---|
| 🟢 Verde | Asistencia válida, dentro de la tolerancia |
| 🔴 Rojo | Fuera de tolerancia, correo no registrado, no matriculado, sesión cerrada, QR que no es un correo o API caída |
| 🟠 Naranja | El estudiante ya tenía registro en esta sesión |

Cada LED queda encendido 2 segundos. Al encender la placa, los tres se prenden un instante como saludo.

---

## Conexión de los LED (protoboard)

| LED | Pin de la ESP32-CAM | Conexión |
|---|---|---|
| Verde | GPIO 13 | GPIO → resistencia de 220 Ω → pata larga del LED; pata corta → GND |
| Rojo | GPIO 14 | Igual |
| Naranja | GPIO 15 | Igual |

No use la ranura microSD: comparte esos pines.

---

## Si algo falla

| Síntoma | Causa probable | Solución |
|---|---|---|
| `pytest` no muestra `20 passed` | Falta instalar algo o la versión de Python no es la 3.12 | Repita la Fase 0 con `py -3.12`; envíe el texto rojo |
| El Serial Monitor muestra puntos y «No se pudo conectar al WiFi» | Nombre o clave mal escritos, red de 5 GHz o red institucional | Revise `WIFI_SSID` y `WIFI_PASSWORD`; use el punto de acceso del celular en 2,4 GHz |
| `esp_camera.h: No such file or directory` al compilar | La placa elegida no es una ESP32 | Instale **esp32 by Espressif** y elija **AI Thinker ESP32-CAM** |
| La página de la placa no abre en el navegador | El PC está en otra red o la IP es otra | Conecte el PC a la misma red que la placa y use la IP del Serial Monitor |
| «Sin conexión con la cámara · reintentando» en la interfaz | IP incorrecta o redes distintas | Igual que el anterior; pase el mouse sobre el mensaje rojo para ver el detalle |
| «La placa responde, pero la cámara no inició» | Cable plano de la cámara suelto | Revise el conector de la cámara OV2640 y pulse RST |
| La cámara se ve, pero no lee el QR | QR pequeño, lejos, desenfocado o con reflejos | Acérquelo hasta que ocupe más o menos ¼ de la imagen, suba el brillo e inclínelo un poco |
| Todo sale en rojo «Fuera de tolerancia» | La clase empezó hace más tiempo que la tolerancia | Use una clase que empiece a la hora actual (Fase 4) |
| La imagen se ve al revés | Orientación de la cámara | En el `.ino`, cambie `H_MIRROR` o `VFLIP` a `1` y súbalo otra vez |
| La placa se reinicia sola | Alimentación insuficiente | Use un cable USB corto y un puerto directo del PC, o un cargador de 5 V / 2 A |
| La interfaz no abre o dice que no hay API | La ventana 1 (uvicorn) está cerrada | Arranque primero la API y después la interfaz |

Si el problema no está en la tabla, tome una captura de la ventana donde aparece el error y de la PowerShell, y envíela.
