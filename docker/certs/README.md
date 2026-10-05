# Certificados de CA adicionales (opcional)

Algunas redes (por ejemplo la red de la UNHEVAL) inspeccionan HTTPS con una CA
propia. Dentro de los contenedores esa CA no es de confianza y `pip`, `npm` y
la descarga de modelos fallan con `CERTIFICATE_VERIFY_FAILED` o
`self-signed certificate in certificate chain`.

Coloca aquí la CA raíz de esa red en formato PEM con extensión `.crt` y vuelve
a construir (`docker compose --env-file .env.docker build`). Las imágenes la
agregan al almacén del sistema; la verificación TLS sigue activa.

Exportarla desde Windows (si TI la instaló en el equipo):

```powershell
certutil -store Root unheval.edu.pe            # muestra el hash del certificado
certutil -store Root <hash> docker\certs\red.cer
certutil -encode docker\certs\red.cer docker\certs\red.crt
del docker\certs\red.cer
```

Los archivos `*.crt` de esta carpeta no se versionan. Fuera de esa red no hace
falta ninguno.
