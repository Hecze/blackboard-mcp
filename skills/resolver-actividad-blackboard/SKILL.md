---
name: resolver-actividad-blackboard
description: >-
  Resuelve una actividad que vive DENTRO de Blackboard (cuestionario, examen en línea, formulario, entrega con
  adjuntos) usando el MCP `blackboard`, que ya trae la sesión del alumno (SSO de Outlook). Avanza página por página
  y se detiene antes de "Enviar": el envío lo hace el alumno. Úsala cuando la alarma diga «actividad» o cuando el
  enunciado no sea un .docx del repo.
---

# resolver-actividad-blackboard

Blackboard se entra por **SSO de Outlook** (con MFA). No hay usuario/contraseña que poner en un archivo: la
"credencial" es la sesión guardada en `~/.blackboard-mcp/` (perfil de Chrome + cookies), y la usan las herramientas
`bb_*` del MCP **blackboard**.

**El navegador de la app (u otro navegador limpio) NO tiene esa sesión**: te va a llevar al portal de acceso. No
intentes iniciar sesión ahí ni pidas la contraseña.

## Antes de empezar (2 minutos)

1. `bb_navegar(url)` con el enlace de la actividad. Devuelve `texto` (la página) y `elementos` (refs numeradas).
2. Lee el `texto`: título, consigna, número de preguntas, **límite de tiempo**, **intentos restantes**.
3. Si la página tiene "Iniciar intento": eso **gasta un intento y arranca el cronómetro**. Avísale al alumno y
   espera su OK antes de pulsarlo.
4. Si la respuesta trae `login_required`: para todo y dile que ejecute `blackboard-mcp login` (SSO + MFA).

## Cómo se trabaja

| Necesitas | Herramienta |
|---|---|
| Abrir la actividad | `bb_navegar(url)` |
| Volver a leer la página / refs nuevas | `bb_ver()` |
| Pulsar un botón o un enlace | `bb_clic(ref)` |
| Escribir en un campo de texto | `bb_rellenar(ref, texto)` |
| Elegir en un desplegable | `bb_elegir(ref, "opción")` |
| Marcar un radio/checkbox | `bb_marcar(ref)` |
| Atrás | `bb_atras()` |
| Enseñar cómo quedó | `bb_captura()` → ruta del PNG |
| Cerrar | `bb_cerrar_navegador()` |

- Las `ref` **caducan** en cuanto la página cambia: usa siempre las del último resultado.
- Un cuestionario con varias preguntas por página: responde las de la página, pulsa **Siguiente**, repite.
- Antes de pasar de página, repasa que cada pregunta de esa página tenga respuesta marcada.

## Regla dura: nunca envíes

- **Nunca** pulses "Enviar", "Enviar intento", "Entregar", "Guardar y enviar" ni "Finalizar intento". `bb_clic` se
  niega (devuelve `bloqueado: true`); si lo ves, es correcto: no busques la forma de saltarlo.
- El cierre es del alumno: revisa, decide y pulsa Enviar.
- Sí puedes pulsar "Guardar" / "Guardar borrador" (no envía) y "Siguiente".

## Al terminar

1. `bb_captura()` y deja la ruta (o muéstrala) para que el alumno vea la última página.
2. Resume en 5-6 líneas: qué respondiste en cada pregunta y por qué, y qué quedó sin responder.
3. Di exactamente qué falta: «está completo, revisa y pulsa Enviar» o «falta la pregunta 7, no tengo el dato».
4. `bb_cerrar_navegador()`.

## Guardarraíles

- No inventes respuestas al azar. Si no tienes el material (lectura, diapositiva, transcripción), pídelo.
- Si el cronómetro corre y no llegas, avisa ya: mejor entregar 8/10 a tiempo que 10/10 tarde.
- Si la actividad pide **adjuntar un archivo**, resuélvelo en el repo (docx/pdf) y súbelo con el selector de
  archivos del formulario; no pegues el contenido en un campo de texto.
- Habla en español y no toques nada fuera de la actividad.
