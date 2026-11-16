# Cómo preparar una evaluación (playbook para el agente)

Procedimiento para que un agente de IA reúna **todo** lo que existe sobre una evaluación de Cibertec (fecha, reglas,
documentos, material de clase y lo que el profesor dijo en cada clase grabada) y le arme al estudiante una guía
de estudio exacta. Está escrito a partir de la preparación real de la **T1 de Base de Datos (GDAT5373)** en
noviembre de 2026: los ejemplos vienen de ese caso.

Las herramientas `bb_*` son del MCP de este repo. Habla con el estudiante en español.

---

## Paso 0 — Sesión de Blackboard (siempre lo primero)

- Lee `~/.blackboard-mcp/session-health.json`. Si `"ok": false`, o si cualquier `bb_*` devuelve `login_required`,
  aplica la alerta **CRÍTICA** de `AGENTS.md` antes de hacer cualquier otra cosa.
- `bb_status` confirma la cuenta y la carpeta de descargas (`download_dir`, por defecto `C:\Users\<usuario>\BlackboardFiles`).

## Paso 1 — Encontrar la evaluación

1. `bb_courses` → ubica el curso. Usa el código (`GDAT5373`) o parte del nombre. Ojo: puede haber cursos repetidos
   de ciclos anteriores; el más reciente sale primero.
2. `bb_evaluations(course="GDAT5373")` → lista cada evaluación con:
   - `due`: fecha límite, en UTC (Lima = UTC−5);
   - `status`: `pending` / `submitted` / `graded` / `overdue`;
   - `attempts_allowed`, `points_possible` y `score`;
   - `instructions` y `teacher_files`: los documentos adjuntos, como la rúbrica o el enunciado;
   - `content_id`: se usa en el paso 2.

   `bb_evaluations(only_open=True)` muestra solo lo que falta entregar.
3. Ten en cuenta:
   - En Cibertec muchas evaluaciones (Examen T1, T2…) **no muestran instrucciones ni preguntas hasta abrirlas**.
     Que salgan vacías no es un error.
   - La fecha de Blackboard **no siempre es la fecha real del examen**. En la T1 de BD, Blackboard decía
     "hasta el 17/11 9:00", pero el profe la tomaba en la última hora de la clase del 16/11 (paso 5).
   - Algunos detalles de configuración no aparecen en `bb_evaluations`. En la T1, **contaba el último intento,
     no el mejor**, no aceptaba entregas tarde y se respondía subiendo archivos. Si importa, se consulta
     `/learn/api/v1/courses/{curso}/contents/{content_id}` (`contentDetail…deploymentSettings`) y la columna de
     notas (`grading.scoringModel`).

## Paso 2 — Leer los documentos de la evaluación

- `bb_download(course, content_id)` baja **todos** los archivos de esa evaluación: los adjuntos, los insertados en
  el texto y, en las evaluaciones Ultra, los que están dentro de las instrucciones (ahí suele estar la rúbrica).
  Quedan en `<download_dir>\<curso>\Downloads\`.
- Busca la **rúbrica** también fuera de la evaluación. En BD estaba en *INFORMACIÓN GENERAL DEL CURSO* y en
  *ENTREGABLES DEL PROYECTO* como `.xlsx`.

## Paso 3 — Bajar todo el material del curso

- `bb_pull_course(course)` baja **todo** a `<download_dir>\<curso>\Todo\`, con las mismas carpetas de Blackboard:
  - archivos de cada semana: PPT, PDF, guías de laboratorio, `.sql`, `.xlsx`, `.rar` (menos de 300 MB);
  - archivos dentro de evaluaciones;
  - **anuncios** en `Todo\ANUNCIOS\`: el texto de cada anuncio como `.txt`, más sus adjuntos. **Los profesores
    publican ahí los scripts de clase** (por ejemplo `LAB 5-11.txt`) y los diagramas (`.graphml` de yEd, `.png`);
  - documentos de **SharePoint**: sílabo, manual de teoría, manual de laboratorio, guía de actividades. Se bajan
    con el inicio de sesión de Microsoft del perfil del navegador.
- Lo que ya se bajó no se vuelve a bajar, así que repetirlo es barato y trae lo nuevo.
- `Todo\manifest.json` es el índice: la ruta de carpetas, el tipo, el texto y los enlaces de cada elemento.
  Úsalo para ubicar cosas sin recorrer carpetas.
- Los enlaces externos (YouTube, por ejemplo) solo quedan anotados en el manifiesto.
- Para leer los archivos: en `.venv` ya están `pypdf` (PDF) y `python-pptx` (PPTX). Extrae el texto a
  `<download_dir>\<curso>\Texto\`. Los `.graphml` son diagramas de yEd (XML) y los `.png` se miran como imagen.

**Dónde puede estar ya descargado algo:**

| Qué | Dónde |
|---|---|
| Todo el curso | `<download_dir>\<curso>\Todo\` (+ `manifest.json`) |
| Archivos de una evaluación o de un elemento | `<download_dir>\<curso>\Downloads\` |
| Solo los PDF, por semana (`bb_sync`) | `<download_dir>\<curso>\<Week NN o carpeta>\` |
| Texto extraído | `<download_dir>\<curso>\Texto\` |
| Transcripciones de clases | `<download_dir>\Grabaciones\<clase TEO/LAB>\<fecha> <id>.md` |
| Guías de estudio ya hechas | `estudio\` en este repo (en `.gitignore`: nunca va al fork público) |

## Paso 4 — El sílabo: peso, semana y descripción oficial

- Abre `Todo\INFORMACIÓN GENERAL DEL CURSO\Sílabo del curso.pdf`. Busca la sección **EVALUACIÓN**: la fórmula
  (T1 20 %, T2 35 %, EF 45 %), la semana y la sesión, y la descripción de cada evaluación. Busca también la
  sección **UNIDADES DE APRENDIZAJE**, que dice qué temas van antes de cada "Evidencia de aprendizaje".
- El sílabo es el punto de partida, **no la última palabra** (ver paso 6).

## Paso 5 — Clases grabadas: qué dijo el profesor

1. `bb_recordings(course)` → grabaciones de las salas de Class del curso (TEO y LAB por separado), con fecha,
   duración y estado. Una que está en `RECORDING` es una clase en vivo; todavía no hay transcripción.
2. `bb_transcript(course)` → guarda la transcripción de **todas** las grabaciones terminadas que falten.
   - Cada línea sale como **🎓 PROFESOR** o **🙋 Alumno: nombre**, con `[hh:mm:ss]` de la grabación, más el
     **chat** (💬) intercalado.
   - Usa la transcripción de Zoom, que tiene buen español y el nombre de cada hablante. Aun así es automática y
     se equivoca en algunas palabras ("Edgar Lean" = Edgar Codd, "Mag Size" = MAXSIZE). Interpreta por contexto.
3. Cada clase dura unas 4 horas (90–170 KB de texto). **Usa un subagente por transcripción**, en paralelo, que la
   lea **entera** en partes, sin saltarse nada. Pídele un informe con:
   - los temas en orden, con marcas de tiempo, y **el último tema visto**;
   - definiciones y criterios **con las palabras del profe** (cómo quiere un DER, qué corrige, qué no acepta);
   - ejercicios resueltos en clase y errores que corrigió;
   - **todo lo dicho sobre la evaluación**, citado con su marca de tiempo;
   - dudas de alumnos y sus respuestas;
   - dudas por errores de transcripción.
4. Para búsquedas rápidas en las transcripciones:
   `examen|T1|T2|evaluaci|va a venir|entra|hasta donde|indicaciones|rúbrica|nota|puntaje|IA|no se olviden|ojo|error`.
   Lo más útil de la T1 de BD salió de frases así:
   - *"la parte teórica va a venir los temas hasta donde llegamos hoy"* (TEO 9/11 [00:18:22]);
   - *"el examen es en la primera sesión de la semana 3… una hora antes se ejecuta"* (LAB 12/11 [03:42:58]);
   - *"totalmente prohibido el uso de la IA para evaluaciones"* (TEO 2/11 [01:52]).
5. Las clases que todavía no tienen transcripción (las de hoy) también pueden traer indicaciones. Avisa al
   estudiante que vuelva a correr `bb_transcript` cuando terminen.

## Paso 6 — Anuncios recientes y alcance final

- `bb_announcements(course, days=30)`: pueden cambiar la fecha, el formato o el alcance.
- Decide el alcance con esta prioridad: **lo que dijo el profesor en clase > anuncios > sílabo > material**.
  Ejemplo real: el sílabo ponía la normalización (Tema 5) en la T1, pero el profe dijo que la teoría llegaba
  "hasta donde llegamos hoy", y ese día el último tema fue *entidad fuerte y débil*. La normalización no entraba.
- Separa teoría y laboratorio si el profe los evalúa juntos. En BD: teoría = clases TEO, laboratorio = clases LAB,
  y **lo que aún no se vio en el LAB no entra** (en la T1, INSERT y SELECT no entraban).

## Paso 7 — Reglas de la evaluación y uso de IA

- Busca en las transcripciones y en los anuncios **si el profesor permite IA** en esa evaluación.
- **Si la prohíbe** (como en la T1 y T2 de BD), el agente **solo ayuda a preparar**: guía, repaso, ejercicios de
  práctica parecidos y explicaciones. **No resuelve la evaluación, no revisa ni corrige las respuestas antes de
  entregarlas, y no se usa durante el examen.** Díselo al estudiante con claridad si lo pide.
- Lo que sí se puede revisar con IA: los ejercicios de práctica del curso (los `Experimentar_*`, casos de las
  diapositivas, actividades no calificadas), y la evaluación **después** de calificada, para aprender de los errores.

## Paso 8 — Escribir la guía

Guárdala en `estudio\<CÓDIGO>-<evaluación>-guia.md`. Estructura que funcionó:

1. **Datos duros arriba**: fecha real (y la de Blackboard si es distinta), intentos y cuál cuenta, formato de
   entrega, peso, uso de IA permitido o no.
2. **Qué entra y qué NO entra** (tabla teoría / laboratorio), con la cita del profe que lo justifica.
3. Por tema: conceptos **con los criterios del profesor**, sintaxis **en su estilo** (sus nombres, sus
   mayúsculas, su forma de escribir PK y FK), y los errores que corrigió en clase.
4. Casos resueltos en clase que conviene rehacer.
5. Rutas a los archivos: transcripciones, scripts de anuncios, diapositivas, rúbrica.

Cita marcas de tiempo (`TEO 9/11 [00:18:22]`) para que el estudiante pueda ir a escuchar la parte exacta.
