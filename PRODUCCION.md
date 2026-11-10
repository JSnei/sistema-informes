# Verificación de preparación para producción

Fecha: 10 de noviembre de 2026.

## Resultado

Las pruebas locales pasan. La conexión y el esquema de PostgreSQL configurado fueron comprobados en una transacción de solo lectura. No se realizó despliegue, ni se enviaron correos, ni se escribieron archivos en Google Drive, ni se modificaron registros de la base real.

No se certifica aún el entorno remoto de producción: faltan las comprobaciones de integraciones y HTTPS indicadas abajo.

## Verificaciones ejecutadas

- **29 pruebas Python: correctas**, ejecutadas con `python -m unittest discover -s tests -v`.
- **10 casos de entrada de precios: correctos**: centenas, miles, millones, centavos, cero, máximo, negativos, texto inválido y exceso de decimales. Los dos scripts JavaScript pasaron comprobación de sintaxis. Se ejecutó `tests/check_frontend.cjs` en el runtime Node disponible.
- Compilación de módulos Python y carga de todas las plantillas Jinja: correctas.
- PostgreSQL: conexión y presencia de las tablas y columnas esperadas, sin escrituras.
- Revisión de las 51 dependencias del proyecto y su árbol de dependencias activo en este equipo: ninguna incompatibilidad detectada.
- `pip check` global detecta conflictos en paquetes ajenos al proyecto (TensorFlow, Streamlit, OpenCV y nbconvert). No se modificaron esos paquetes. Usar un entorno virtual exclusivo para el despliegue.
- `git diff --check`: sin errores de contenido. Puede aparecer una advertencia informativa de conversión de saltos de línea de Windows.

### Cobertura funcional

Creación, duplicados y edición de tickets; solicitudes `000`; validación de tienda; teléfono; precios; filtros; XLSX; edición de informes; anulación; eliminación de pruebas; enlace de un solo uso sin vencimiento; renovación que invalida el enlace anterior; rechazo de enlaces cancelados; permisos de todas las rutas administrativas; sesiones manipuladas o vencidas; acceso de operadores 400/401; OTP con expiración, espera entre envíos, máximo de intentos y bloqueo de doble verificación simultánea; rechazo de suplantación del técnico; escape de HTML y textos que parecen fórmulas de Excel.

Las pruebas HTTP usan SQLite en memoria, HTTPS simulado y servicios de correo/Drive sustituidos. La comprobación real de PostgreSQL fue de lectura: **no se ha probado carga ni concurrencia de escrituras sobre PostgreSQL, restauración de respaldos o comportamiento en un navegador real**. Los casos JavaScript usan elementos DOM simulados.

## Fallos corregidos durante la revisión

1. Códigos de técnicos y operadores sin caducidad ni límite de intentos: ahora tienen 10 minutos, 5 intentos, espera de 60 segundos entre solicitudes y un solo uso. La misma lógica se aplica al administrador.
2. Generación de informes sin sesión de técnico: ahora exige su sesión, su identidad y su fecha de servicio; también valida el mínimo de 25 palabras en el servidor.
3. Rutas antiguas de servicios externos que no verificaban el vencimiento de sesión del operador: ahora lo comprueban. Se admite correctamente al operador del rango 401–499.
4. Generadores antiguos que producían enlaces sin ticket, incompatibles con el formulario actual: ahora dirigen al registro de tickets.
5. Textos de usuarios interpretables como fórmulas en `Servicios.xlsx`: ahora se exportan como texto, como ya se hacía en `Software V2.xlsx`.
6. Validación de longitudes y campos obligatorios antes de guardar informes para evitar errores de PostgreSQL.
7. Perfiles inconsistentes en el formulario de edición de técnicos y validación JavaScript ejecutada antes de cargar el formulario.
8. Errores de validación de negocio que terminaban en error 500: ahora muestran una página de error 400.

## Pendientes del entorno

En este equipo se detectó:

- Python 3.10.11; el SDK de Google instalado informa fin de soporte de Python 3.10. Preparar un entorno aislado con Python 3.11 o superior y repetir las pruebas allí.
- `APP_ENV` no está definido como `production`.
- Las credenciales de Drive no son accesibles en la ruta configurada/por defecto. Configurar `GOOGLE_DRIVE_CREDENTIALS` con la ruta del archivo en el servidor y verificar permisos del archivo y de la carpeta remota.
- `COOKIE_SECURE=true` y una clave de sesión de al menos 32 caracteres sí están configurados.

No se modificó `.env` ni se copiaron secretos a este informe.

## Secuencia de despliegue

1. En el servidor, preparar un entorno virtual exclusivo con Python 3.11 o superior. Instalar `requirements-test.txt`, ejecutar `python -m pip check` y repetir `python -m unittest discover -s tests -v`. Las dependencias no están fijadas a versiones; repetir estas comprobaciones en el entorno que se vaya a publicar.
2. Configurar las variables existentes de PostgreSQL, Resend, correo administrativo/operador y Google Drive. Añadir `APP_ENV=production`; mantener `COOKIE_SECURE=true` y `SESSION_SECRET` estable y suficientemente largo.
3. Ejecutar `python scripts/verificar_produccion.py --database`. Debe terminar sin requisitos pendientes. El script no muestra secretos y no escribe en PostgreSQL.
4. Respaldar PostgreSQL antes de iniciar la nueva versión. El inicio de la aplicación crea tablas faltantes y agrega las columnas `telefono_tecnico` y `precio` si faltan; no hay un sistema de migraciones versionadas. Probar previamente este inicio sobre una copia del esquema de producción y comprobar una restauración del respaldo.
5. Ejecutar **una sola instancia de aplicación y un solo worker**, sin `--reload`: `python -m uvicorn main:app --host 127.0.0.1 --port 8000 --workers 1`. Los códigos OTP se guardan en memoria; varios workers o réplicas no comparten esos códigos. Reiniciar la aplicación invalida códigos pendientes. Para escalar, mover este almacenamiento a un servicio compartido antes de aumentar instancias.
6. Publicar mediante el proxy HTTPS del servidor. Si el proxy termina HTTPS, configurar encabezados reenviados solo desde su dirección de confianza. Verificar que los enlaces copiados usen el dominio público y `https://`, y que las cookies permitan completar el login.
7. En el entorno de preproducción, comprobar envío y recepción reales de OTP y escritura de ambos XLSX en la carpeta de Drive. Hacer una prueba completa de ticket → enlace → informe → edición → descarga. Confirmar que el enlace usado y el anterior a una renovación no funcionen.
8. Sobre una base de preproducción aislada, comprobar envíos simultáneos del mismo enlace y la renovación mientras se intenta guardar: solo debe persistir un servicio. No se ha hecho esta prueba sobre la base real para evitar escrituras de prueba.

Si Drive falla, el servicio ya guardado se conserva; revisar logs y comprobar la sincronización antes de dar por actualizado el Excel. La sincronización se ejecuta dentro de la petición, por lo que también debe medirse su tiempo con la carpeta real.
