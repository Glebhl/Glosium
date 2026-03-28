# LexiForge

## Descripcion general

LexiForge es un prototipo de escritorio para el aprendizaje de idiomas asistido por IA, construido con `PySide6`, `Qt WebEngine` y una interfaz HTML/CSS/JavaScript. La aplicacion permite que el estudiante describa lo que quiere estudiar, muestra en streaming tarjetas de vocabulario generadas por OpenAI y luego construye una leccion a partir de esas tarjetas mediante un pipeline de dos etapas.

## Estructura del proyecto

```text
LexiForge/
|-- main.py                         # Punto de entrada de la aplicacion
|-- settings.yaml                   # Configuracion de runtime para idiomas, modelos y opciones del pipeline
|-- app/                            # Shell de la aplicacion, enrutamiento, logging y helpers de configuracion
|   |-- backend.py
|   |-- router.py
|   |-- settings.py
|   |-- logging_config.py
|   |-- exception_logging.py
|   `-- language_registry.py
|-- models/                         # Modelos tipados para tarjetas, pasos del macro plan y ejercicios generados
|-- pipeline/                       # Generacion de vocabulario, planificacion macro, generacion de tareas y parsing
|-- llm_gateway/                    # Wrappers del cliente de OpenAI y helpers de cache
|-- prompts/                        # Plantillas de prompts usadas por el pipeline de generacion
|-- dev_fixtures/                   # Fixtures locales opcionales para desarrollo y depuracion
|-- ui/
|   |-- controllers/                # Controladores de pantallas, incluida la configuracion, carga y flujo de leccion
|   |-- services/                   # Workers en segundo plano y servicios del lado de la UI
|   |-- views/                      # Pantallas HTML/CSS/JS
|   `-- assets/                     # Archivos de tema compartidos y recursos estaticos
`-- i18n/                           # Documentacion localizada del proyecto
```

## Como funciona

1. El estudiante introduce una solicitud de estudio en la pantalla de configuracion.
2. La aplicacion genera tarjetas de vocabulario y las muestra en la UI a medida que llegan.
3. Cuando el estudiante inicia la leccion, la aplicacion abre una pantalla de carga.
4. Un worker en segundo plano crea un macro plan de leccion a partir de las tarjetas seleccionadas.
5. El generador de tareas expande ese plan en ejercicios concretos para la pantalla principal de la leccion.

## Primeros pasos

### 1. Clona el repositorio

```bash
git clone https://github.com/Glebhl/LexiForge.git
cd LexiForge
```

### 2. Crea y activa un entorno virtual

```bash
python -m venv .venv
.venv\Scripts\Activate.ps1
```

### 3. Instala las dependencias

```bash
pip install -r requirements.txt
```

### 4. Configura las variables de entorno

Crea un archivo `.env` en la raiz del proyecto:

```env
OPENAI_API_KEY=your_openai_api_key_here
```

Sin `OPENAI_API_KEY`, la generacion de tarjetas y la generacion de lecciones en vivo no funcionaran.

### 5. Ajusta la configuracion de runtime

Edita `settings.yaml` para elegir los idiomas de la leccion, el nivel del estudiante, la asignacion de modelos y las opciones del pipeline:

```yaml
lesson:
  language: en
  lerner_language: ru
  learner_level: B2
models:
  card_generation: gpt-5.4-nano
  lesson_planning: o3
  task_generation: gpt-5.4-mini
  answer_matcher: gpt-5.4-nano
pipeline:
  card_generation:
    reasoning_effort: none
    text_verbosity: low
    service_tier: flex
  lesson_planning:
    reasoning_effort: low
    text_verbosity: null
    service_tier: flex
  task_generation:
    reasoning_effort: none
    text_verbosity: low
    service_tier: flex
  answer_matcher:
    reasoning_effort: none
    text_verbosity: low
    service_tier: flex
```

### 6. Ejecuta la aplicacion

```bash
python main.py
```

## Notas de desarrollo

- `dev_fixtures` puede precargar tarjetas o sustituir la generacion en vivo de la leccion con datos fixture durante el desarrollo.
- Los archivos de prompts en `prompts/en/` controlan tanto la planificacion macro como la generacion de tareas.

Para depuracion, puedes agregar estos parametros al archivo `.env`:

```env
GLOSIUM_DEV_CARDS=1
GLOSIUM_DEV_MACRO_PLAN=1
GLOSIUM_DEV_LESSON=1
GLOSIUM_DEV_CARDS_FILE=dev_fixtures/cards.json
GLOSIUM_DEV_MACRO_PLAN_FILE=dev_fixtures/macro_plan.txt
GLOSIUM_DEV_LESSON_FILE=dev_fixtures/lesson.json
```

## Estado

El proyecto sigue siendo un prototipo. La version actual admite generacion de vocabulario con IA, planificacion macro de lecciones y contenido de tareas generado.

## Hoja de ruta

Los siguientes pasos previstos incluyen:

- Agregar guia de IA y explicaciones de errores
- Agregar soporte para mas idiomas
- Agregar soporte de gramatica
- Agregar localizaciones ademas del ingles
- Agregar seguimiento del progreso

## Contribuciones

Se agradecen issues, sugerencias y pull requests.
