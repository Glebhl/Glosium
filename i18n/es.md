# LexiForge

LexiForge es un prototipo de escritorio para aprendizaje de idiomas construido con `PySide6`, `Qt WebEngine` y una interfaz HTML/CSS/JavaScript. La aplicacion genera tarjetas de vocabulario con OpenAI y luego ejecuta una leccion basada en el contenido elegido.

## Capacidades actuales

- Generacion de tarjetas de vocabulario mediante OpenAI Responses API
- Flujo de leccion con tareas de tipo explanation, matching, translation, filling y question
- Dev fixtures para tarjetas, macro plan y plan temporal de leccion

## Estructura del proyecto

```text
LexiForge/
|-- main.py                         # Punto de entrada de la aplicacion
|-- app/                            # Infraestructura de la aplicacion y utilidades compartidas
|   |-- backend.py                  # Puente Python <-> UI mediante Qt
|   |-- router.py                   # Navegacion entre pantallas
|   |-- logging_config.py           # Configuracion de logging
|   |-- exception_logging.py        # Logging global de excepciones y callbacks
|   `-- language_registry.py        # Registro de idiomas y helpers
|-- dev_fixtures/                   # Datos locales de fixtures y configuracion de carga
|   |-- settings.py
|   |-- cards.json
|   |-- macro_plan.txt
|   `-- lesson.json
|-- llm_gateway/                    # Wrappers de OpenAI y cache
|-- pipeline/                       # Generacion de tarjetas, planes y tareas
|-- prompts/                        # Plantillas de prompts
`-- ui/
    |-- controllers/                # Controladores de pantallas
    |-- services/                   # Servicios auxiliares del nivel UI
    |-- views/                      # Pantallas HTML/CSS/JS
    `-- assets/                     # Fuentes, iconos y estilos compartidos
```

## Inicio rapido

```bash
python -m venv venv
venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main.py
```
