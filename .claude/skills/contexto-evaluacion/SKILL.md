---
name: contexto-evaluacion
description: Reúne TODO lo que existe sobre una evaluación de un curso de Cibertec en Blackboard (T1, T2, examen final, entregable, proyecto…) — fecha real, reglas, intentos, rúbrica, enunciado, sílabo, material del curso, anuncios y lo que el profesor dijo en cada clase grabada — y lo deja en un expediente con fuentes citadas. Úsala cuando haya que trabajar sobre una evaluación concreta, sea cual sea el fin (estudiar, practicar, entender una nota, revisar lo aprendido). Argumentos: evaluación y curso, p. ej. "T1 base de datos".
---

# contexto-evaluacion

Construye el **expediente** de una evaluación: todos los datos disponibles sobre ella, verificados y con su
fuente. No decide qué hacer con ellos; eso lo dice la petición del usuario. El expediente es la base para
cualquier tarea posterior.

Entrada: `<evaluación> <curso>`, por ejemplo `T1 base de datos` o `examen final GDAT5373`.
Salida: `estudio/<CÓDIGO>-<evaluación>/` en este repo (la carpeta `estudio/` está en `.gitignore`: nunca va al
fork público). Contiene `EXPEDIENTE.md` y los informes por clase.

Las herramientas `bb_*` son del MCP de este repo (servidor `blackboard`). Si no están cargadas, búscalas con
ToolSearch ("blackboard"). Habla con el estudiante en español.

---

## 0. Sesión

- Lee `~/.blackboard-mcp/session-health.json`. Si dice `"ok": false`, o si una `bb_*` devuelve `login_required`,
  aplica primero la alerta **CRÍTICA** de `AGENTS.md`. Sin sesión no hay expediente.
- `bb_status` → cuenta y `download_dir` (por defecto `C:\Users\<usuario>\BlackboardFiles`).

## 1. Identificar el curso y la evaluación

1. `bb_courses` → curso por código o nombre. Puede haber cursos repetidos de ciclos anteriores; el más reciente
   sale primero. Confirma con el código (`GDAT5373`).
2. `bb_evaluations(course=…)` → busca la evaluación por nombre ("Examen T1", "T1", "EF", "Entregable al 50%"…).
   Anota `due` (en UTC; Lima = UTC−5), `status`, `attempts_allowed`, `points_possible`, `score`, `feedback`,
   `instructions`, `teacher_files` y `content_id`.
   - Si hay varias candidatas, anótalas todas y explica cuál elegiste.
   - Muchas evaluaciones de Cibertec **no muestran instrucciones ni preguntas hasta abrirlas**: que salgan
     vacías no es un error.
3. **Configuración que `bb_evaluations` no muestra.** Consúltala con la sesión (`blackboard_mcp.bb.Blackboard`,
   desde `.venv`):
   - `GET /learn/api/public/v2/courses/{curso}/gradebook/columns/{column_id}` → `grading.scoringModel`
     (`Last` = cuenta el **último** intento, `Highest` = el mejor), `attemptsAllowed`, `due`.
   - `GET /learn/api/v1/courses/{curso}/contents/{content_id}` → `contentDetail…test.deploymentSettings`:
     `isLateAttemptCreationDisallowed`, `allowFileSubmission` y `allowTextSubmission` (indican cómo se responde),
     y si hay límite de tiempo o contraseña.

## 2. Documentos de la evaluación

- `bb_download(course, content_id)` → adjuntos, archivos insertados y, en evaluaciones Ultra, los archivos dentro
  de las instrucciones (rúbrica, enunciado, plantillas). Quedan en `<download_dir>\<curso>\Downloads\`.
- La **rúbrica** puede estar en otra parte. En BD estaba como `.xlsx` en *INFORMACIÓN GENERAL DEL CURSO* y en
  *ENTREGABLES DEL PROYECTO*. Búscala en el manifiesto del paso 3: `rúbrica|rubrica|criterio|lineamiento`.
- Extrae los **criterios y niveles** de la rúbrica tal cual, sin resumirlos.

## 3. Todo el material del curso

- `bb_pull_course(course)` baja todo a `<download_dir>\<curso>\Todo\`, con las mismas carpetas de Blackboard:
  - archivos de cada semana: PPT, PDF, guías, `.sql`, `.xlsx`; los de más de 300 MB se omiten;
  - archivos dentro de evaluaciones;
  - **anuncios**, en `Todo\ANUNCIOS\` (texto y adjuntos). **Los profesores publican ahí los scripts de clase y los
    diagramas**;
  - documentos de **SharePoint** (sílabo, manuales, guía de actividades), con el inicio de sesión de Microsoft del
    perfil del navegador.

  Lo ya bajado no se repite, así que vuelve a correrlo siempre: trae lo nuevo.
- `Todo\manifest.json` = índice de todo: la ruta de carpetas, el tipo, el texto y los enlaces de cada elemento.
- Extrae el texto a `<download_dir>\<curso>\Texto\` con `pypdf` y `python-pptx` (están en `.venv`; ejecuta con
  `python -I`). Los `.graphml` son diagramas de yEd (XML) y los `.png` se miran como imagen.

**Dónde puede estar ya algo descargado:**

| Qué | Dónde |
|---|---|
| Curso completo + índice | `<download_dir>\<curso>\Todo\` y `Todo\manifest.json` |
| Archivos de un elemento o evaluación | `<download_dir>\<curso>\Downloads\` |
| Solo los PDF, por semana (`bb_sync`) | `<download_dir>\<curso>\<Week NN o carpeta>\` |
| Texto extraído | `<download_dir>\<curso>\Texto\` |
| Transcripciones de clases | `<download_dir>\Grabaciones\<sala TEO/LAB>\<fecha> <id>.md` |
| Expedientes y guías anteriores | `estudio\` en este repo |

## 4. Sílabo: la versión oficial

`Todo\INFORMACIÓN GENERAL DEL CURSO\Sílabo del curso.pdf`:
- **EVALUACIÓN**: la fórmula y el peso, la semana y la sesión, la descripción oficial y las consideraciones
  (nota mínima, sustitutorio…).
- **UNIDADES DE APRENDIZAJE**: qué temas van antes de cada "Evidencia de aprendizaje" de esa evaluación.

El sílabo es la versión oficial, **no la última palabra**: el profesor la ajusta en clase (paso 6).

## 5. Clases grabadas: lo que dijo el profesor

1. `bb_recordings(course)` → grabaciones de las salas de Class del curso (TEO y LAB por separado). Una en
   `RECORDING` es una clase en vivo y todavía no tiene transcripción.
2. `bb_transcript(course)` → guarda las transcripciones que falten. Cada línea sale como **🎓 PROFESOR** o
   **🙋 Alumno: nombre**, con `[hh:mm:ss]` de la grabación y el chat (💬) intercalado. Viene de Zoom, así que es
   buena pero automática: corrige por contexto ("Edgar Lean" = Edgar Codd, "Mag Size" = MAXSIZE).
3. Lanza **un subagente por transcripción, en paralelo**. Cada clase dura unas 4 h (90–170 KB). Que la lea
   **entera** en partes y guarde su informe en `estudio/<CÓDIGO>-<evaluación>/clases/<fecha>-<TEO|LAB>.md` con:
   - los temas en orden, con marcas de tiempo, y **el último tema visto**;
   - definiciones y criterios **con las palabras del profesor** (qué exige, qué corrige, qué no acepta, su
     notación y su estilo de código);
   - ejercicios resueltos y errores corregidos;
   - **todo lo dicho sobre evaluaciones**: fecha, formato, alcance, cómo califica, qué "va a venir", uso de IA.
     Cada cosa citada con su marca de tiempo;
   - dudas de alumnos con la respuesta del profesor;
   - las partes dudosas por errores de transcripción.
4. Patrones para búsquedas rápidas:
   `examen|T1|T2|EF|evaluaci|va a venir|entra|hasta donde|indicaciones|rúbrica|nota|puntaje|calific|IA|ojo|error|no se olviden`.
5. Si hay clases antes de la evaluación que aún no están transcritas, anótalo como **pendiente** en el expediente.

## 6. Anuncios y decisión de alcance

- `bb_announcements(course, days=60)` → cambios de fecha, formato o alcance. Los anuncios también quedan en
  `Todo\ANUNCIOS\`.
- Resuelve cada dato con esta prioridad: **profesor en clase (más reciente primero) > anuncios > configuración en
  Blackboard > sílabo > material**. Si hay conflicto, regístralo con las dos fuentes.
  - Ejemplo real (T1 de BD): el sílabo ponía la normalización en la T1. El profesor dijo *"hasta donde llegamos
    hoy"* (TEO 9/11 [00:18:22]), y ese día el último tema fue entidad fuerte y débil. Además, Blackboard decía
    "hasta el 17/11 9:00", pero el profesor la tomaba en la última hora de la clase del 16/11 (LAB 12/11 [03:42:58]).
- Si la evaluación mezcla teoría y laboratorio, separa el alcance de cada uno (salas TEO y LAB). Lo que todavía no
  se vio en una de ellas no entra en esa parte.

## 7. Escribir `EXPEDIENTE.md`

Los hechos van con su fuente, sin recomendaciones ni consejos. Estructura:

1. **Identificación**: curso, evaluación, `content_id` y `column_id`, enlace de Blackboard.
2. **Datos duros**: fecha real y fecha de Blackboard, intentos y cuál cuenta, entregas tarde, formato de respuesta
   (archivo o texto), tiempo, peso en el promedio, nota mínima, estado y nota actual.
3. **Reglas dichas por el profesor**: uso de IA, materiales permitidos, modalidad. Cita y marca de tiempo de cada una.
4. **Alcance**: tabla de qué entra y qué no entra (teoría / laboratorio), con la cita que lo justifica.
5. **Criterios de evaluación**: rúbrica completa (criterios, niveles, puntajes), más lo que el profesor dijo que
   exige o penaliza.
6. **Contenido por tema dentro del alcance**: conceptos con los criterios del profesor, sintaxis en su estilo y
   errores que corrigió en clase. Enlaza a los informes de `clases/`.
7. **Ejercicios y casos de referencia**: los resueltos en clase y los de práctica del curso (`Experimentar_*`,
   actividades), con su ruta.
8. **Conflictos y pendientes**: fuentes que se contradicen, clases sin transcripción y datos que no se encontraron.
9. **Índice de fuentes**: la ruta de cada archivo usado.

Al terminar, dile al usuario dónde está el expediente y resume los datos duros, el alcance y los pendientes.
Lo que se haga después con el expediente (estudiar, practicar, analizar) lo decide la petición del usuario. Si
esa petición choca con una regla del profesor registrada en el punto 3 (por ejemplo, IA prohibida en la
evaluación), dilo antes de seguir.
