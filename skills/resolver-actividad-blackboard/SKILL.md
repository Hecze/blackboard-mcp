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

## Regla dura: nunca envíes (salvo permiso explícito)

- **Nunca** pulses "Enviar", "Enviar intento", "Entregar", "Guardar y enviar" ni "Finalizar intento" con `bb_clic`:
  se niega (devuelve `bloqueado: true`); si lo ves, es correcto: no busques la forma de saltarlo.
- El cierre es del alumno: revisa, decide y pulsa Enviar. **Salvo que lo autorice explícitamente en la conversación**
  («envíalos tú»): entonces usa `bb_enviar(ref)`, que pulsa el botón de envío y luego su confirmación
  («¿Desea enviar el examen?»). Son dos llamadas: la primera abre el modal, la segunda lo confirma.
- Sí puedes pulsar "Guardar" / "Guardar borrador" (no envía) y "Siguiente".

## Barreras conocidas (ya resueltas: no las redescubras)

- **Las opciones no salen en el snapshot** → el texto de la pregunta y las `ref` viven en shadow DOM; el snapshot ya
  lo recorre. Si ves una pregunta sin opciones, es que el snapshot es viejo: `bb_ver()`.
- **`bb_clic` dice que la ref no existe** → la página se re-renderizó. No insistas con la misma ref: `bb_ver()` y usa
  las nuevas (el propio tool intenta recuperarla por texto).
- **El clic en "Iniciar/Continuar intento" parece no hacer nada** → abrió el reproductor en **otra pestaña**; el tool
  ya se cambia solo. Si insistes dos veces, puedes abrir dos intentos: mira el número de "intentos restantes" antes.
- **"Enviar" aparece deshabilitado** con todo respondido → normal hasta que el contador de pendientes llega a 0 en el
  siguiente render. No es motivo para salir y volver a entrar.
- **La sesión caduca** → `login_required` en la respuesta. No hay contraseña que probar: el alumno corre
  `blackboard-mcp login`.
- **Se cerró el navegador / se cayó la sesión de trabajo** → abre la actividad otra vez y pulsa "Continuar intento":
  el borrador está guardado y no gasta intento (solo se gasta al enviar o al agotarse el tiempo).

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
