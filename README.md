# Post Office API

API backend del proyecto de Servidor de Correos Electrónicos desarrollado para la materia de Redes de Computadores.

## Descripción

Este es el backend del sistema Post Office, una API REST que implementa un servidor de correos electrónicos personalizado con funcionalidades completas de gestión de correo.

## Tecnologías Utilizadas

- **Python**: Lógica principal del servidor
- **Docker**: Containerización de la aplicación

## Características

- Servidor de correos electrónicos completo
- API REST para gestión de correos
- Soporte para múltiples usuarios
- Protocolos de correo estándar
- Sistema de autenticación y autorización

## Requisitos

- Python 3.8 o superior
- pip (gestor de paquetes de Python)
- Docker (opcional)

## Instalación

### Método 1: Instalación Local

```bash
# Clonar el repositorio
git clone https://github.com/NastMz/Post-Office-API.git
cd Post-Office-API

# Crear entorno virtual
python -m venv venv

# Activar entorno virtual
# Windows
venv\Scripts\activate
# Linux/macOS
source venv/bin/activate

# Instalar dependencias
pip install -r requirements.txt
```

### Método 2: Docker

```bash
# Construir imagen
docker build -t post-office-api .

# Ejecutar contenedor
docker run -p 8000:8000 post-office-api
```

## Configuración

Configurar las variables de entorno necesarias para el funcionamiento del servidor de correos:

```bash
# Crear archivo de configuración
cp .env.example .env

# Editar configuración según necesidades
nano .env
```

## Ejecución

### Desarrollo Local
```bash
# Ejecutar servidor de desarrollo
python app.py

# O usando uvicorn (si usa FastAPI)
uvicorn main:app --reload
```

### Producción
```bash
# Ejecutar usando Gunicorn
gunicorn app:app

# O usando el Procfile configurado
```

## Protocolo de Correo

La API implementa funcionalidades similares a los protocolos estándar de correo:
- SMTP para envío de correos
- POP3/IMAP para recepción de correos
- Gestión de buzones de entrada y salida

## Testing

```bash
# Ejecutar pruebas
python -m pytest

# Ejecutar con cobertura
python -m pytest --cov=app
```

## Frontend Integration

Esta API está diseñada para trabajar con el frontend disponible en: [Post-Office](https://github.com/NastMz/Post-Office)

## Deployment

### Heroku
El proyecto incluye un `Procfile` para despliegue en Heroku:

```bash
# Crear aplicación Heroku
heroku create post-office-api

# Desplegar
git push heroku main
```

### Docker
```bash
# Push a registro de contenedores
docker tag post-office-api your-registry/post-office-api
docker push your-registry/post-office-api
```

## Proyecto Académico

Este proyecto fue desarrollado como parte del curso de **Redes de Computadores**, implementando los conceptos fundamentales de:
- Protocolos de red
- Arquitectura cliente-servidor
- Sistemas de correo electrónico
- APIs REST
