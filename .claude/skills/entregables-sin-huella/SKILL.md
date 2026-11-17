---
name: entregables-sin-huella
description: >-
  Redacta y empaqueta entregables (Word/PDF, scripts SQL, diagramas) en el registro del alumno y sin huellas de
  herramienta: sin metarreferencias ("opción autorizada en las indicaciones"), sin ecos de la rúbrica, sin cabeceras
  decorativas en el SQL y con los metadatos del archivo a nombre del alumno. Úsala SIEMPRE antes de entregar un
  documento, un script o un diagrama.
---

# entregables-sin-huella

## 0. Principio y límite

- Lo que se evita son **huellas accidentales** (metadatos de la herramienta, registro de plantilla corporativa,
  frases que solo aparecen cuando alguien "redacta para una rúbrica") y que el alumno **no pueda sustentar** lo
  que entrega. La profesora de ADSI lo dice explícito: *"si no saben explicar qué elementos utilizaron, sus
  puntajes bajan"*.
- **No** se falsifica autoría (firmas, QR, declaraciones juradas) ni se oculta el uso de IA donde el curso exige
  declararlo. Si el curso prohíbe IA, avisa **antes** de empezar (regla de `AGENTS.md` y de
  `obtener-contexto-evaluacion` §0).

## 1. Señales que delatan un texto generado

| Señal | Ejemplo real (T1 de ADSI, 16/11) | Cómo se escribe |
|---|---|---|
| Definir el concepto que te evalúan | "El MCUN representa la vista externa del negocio: los ON (dirección), los CUN (procesos que entregan valor)…" | No definas lo que el profesor ya enseñó. Empieza por lo que hiciste |
| Justificar el cumplimiento de la consigna | "los diagramas se elaboraron con draw.io (**opción autorizada en las indicaciones de la evaluación**)" | Fuera. El profesor conoce su consigna; citarla para defenderte es firma de IA |
| Copiar la rúbrica | "…**enfocados a los CUN identificados**" (frase literal de la rúbrica) | Di lo mismo con tus palabras: "cada objetivo apunta a los procesos de la tabla" |
| Tercera persona y simetría perfecta | todos los párrafos del mismo largo, sin "yo", sin frases cortas | Primera persona, párrafos desiguales, alguna frase de 5 palabras |
| Puntuación "de ensayo" | "—", "«»", ";" en cada oración | Coma y punto. Las comillas angulares solo si el material del curso las usa |
| Cierre que repite lo dicho | "Decisiones de modelado" con 5 viñetas que resumen las tablas | Un párrafo corto con lo que te van a preguntar en la sustentación |
| Adjetivos vacíos | "solución integral", "enfoque robusto", "de manera eficiente" | Concretos: qué, cuánto, dónde |
| Meta-narración del entregable | "A continuación se presentan…", "En conclusión…" | Nada. Ve directo |

## 2. Voz

- **Primera persona y pasado simple**: "armé", "usé", "puse", "saqué".
- Referencias reales a la clase o al material: "según el manual", "como vimos en la sesión", "la convención CUN-###".
  Solo si es cierto.
- Tablas: celdas cortas. Una justificación de 3 líneas basta; un párrafo perfecto de 6 líneas en cada celda canta.
- Deja **una o dos** imperfecciones naturales (una repetición, una frase telegráfica). No las forces: se nota igual.
- Si el curso pide "sustento", escríbelo como se lo explicarías a un compañero, no como una norma.

## 3. Metadatos

Comprobar siempre antes de subir:

| Archivo | Dónde | Qué mirar |
|---|---|---|
| `.docx` | `docProps/core.xml` | `dc:creator`, `cp:lastModifiedBy`, `dc:title`. Si dice `python-docx`, un nombre de usuario ajeno o el título de otra empresa → corregir |
| `.docx` | `docProps/app.xml` | `Application`, `Company`, `TotalTime` (aquí llegó a decir `Company: Windows uE` y `Title: La Empresa JUNTOS SAC`, heredado de la plantilla del docente) |
| `.pdf` | `/Author`, `/Title`, XMP | El PDF sale con lo que tenía el Word: si el Word está limpio, el PDF también |
| `.png` | chunks `tEXt` | draw.io no escribe metadatos (bien); otras herramientas sí |

`python scripts/limpiar_metadatos.py archivo.docx --autor "Nombre Alumno" --titulo "T1 – MCUN"` (y lo mismo con el
PDF). Nunca dejes el nombre del docente como último modificador si el archivo ya es tuyo.

## 4. Scripts SQL (SQL Server)

Lo que delata a un generador:

```sql
/* ============================================================
   PROYECTO : BD_NEGOCIO_ABC
   AUTOR    : ...
   FECHA    : ...
   ============================================================ */
SET NOCOUNT ON;
IF OBJECT_ID('dbo.CLIENTES','U') IS NOT NULL DROP TABLE dbo.CLIENTES;
CREATE TABLE dbo.CLIENTES (
    rut         VARCHAR(12) NOT NULL,   -- RUT del cliente
    nombre      VARCHAR(60) NOT NULL,   -- nombre completo
    CONSTRAINT PK_CLIENTES PRIMARY KEY (rut),
    CONSTRAINT FK_... FOREIGN KEY ... ON DELETE CASCADE
);
```

Señales: cabecera decorativa, comentario en **cada** columna, `IF OBJECT_ID … DROP` en todas las tablas,
`dbo.` en todo, nombres de `CONSTRAINT` sistemáticos, indentación perfecta de 4 espacios, `SET NOCOUNT ON`,
bloques `-- =====`, emojis, "Autor/Fecha/Versión", `ON DELETE CASCADE` porque sí.

Cómo escribe un alumno en un examen:

```sql
CREATE DATABASE BD_NEGOCIO_ABC
ON( NAME = BDNEG_Prin, FILENAME = 'C:\BD_NEGOCIO\DATOS\BDNEG_Prin.mdf', SIZE = 20MB, MAXSIZE = 350MB, FILEGROWTH = 8% )
LOG ON( NAME = BDNEG_log, FILENAME = 'C:\BD_NEGOCIO\TRANS\BDNEG_log.ldf', SIZE = 10MB, MAXSIZE = 150MB, FILEGROWTH = 7% )
GO
USE BD_NEGOCIO_ABC
GO
CREATE TABLE CLIENTES(
 rut VARCHAR(12) NOT NULL PRIMARY KEY,
 nombre VARCHAR(60) NOT NULL,
 direccion VARCHAR(80) NOT NULL,
 telefono VARCHAR(15) NOT NULL)
GO
```

Reglas:

- **Sí** debe estar lo que pide el enunciado: PK, FK, NULL/NOT NULL, tipos, tamaños de archivo, `GO`.
- **No** debe estar: cabecera, comentarios por columna, `IF EXISTS` preventivos, `dbo.`, `SET NOCOUNT ON`,
  nombres de constraint con prefijo, CASCADE, `PRINT '...'`.
- Un comentario suelto y en su jerga (`-- detalle de la reserva va con pk compuesta`) es humano; diez comentarios
  alineados no.
- Sangría: consistente pero no perfecta. Mayúsculas en tablas, como en clase.

## 5. Diagramas y otros entregables

- Exporta **PNG** sin marca de agua ni pie "generado con…". Si entregas el fuente (`.drawio`, `.graphml`), que el
  nombre del archivo sea neutro (`MCUN_1_casos_uso.drawio`, no `generado_por_agente.drawio`).
- No inventes capturas ni "pantallazos" que no correspondan a una ejecución real.
- Código de programa: sin comentarios obvios (`// suma 1 al contador`), sin docstrings de todas las funciones en un
  trabajo de 20 líneas.

## 6. Checklist antes de subir

- [ ] El texto empieza por lo que hice, no por la definición del concepto.
- [ ] No cito la consigna ni la rúbrica dentro de la respuesta.
- [ ] No hay "en conclusión", "a continuación", "de manera eficiente".
- [ ] Primera persona al menos una vez por sección.
- [ ] `core.xml` / `/Author` con el nombre del alumno; sin `python-docx`, sin nombre del docente.
- [ ] El SQL no tiene cabecera ni comentarios por columna.
- [ ] Puedo explicar cada elemento sin leer: actores, número de casos de uso, de dónde salió cada objetivo.
