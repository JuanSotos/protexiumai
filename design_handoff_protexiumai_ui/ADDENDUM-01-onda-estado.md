# Addendum 1 — Animación de onda en el semáforo de estado

Añadido después de la primera entrega del README. Afecta solo al indicador de estado de la barra lateral ("Estado del equipo"). Todo lo demás del README sigue igual.

## Qué es
El punto central del semáforo emite ondas concéntricas que crecen hacia fuera y se desvanecen, como un radar. Comunica que la vigilancia está activa y en marcha, no solo que el estado es correcto.

## Composición
Contenedor de 44 × 44 px, `position:relative`, contenido centrado. Dentro, en este orden:

1. **Tres anillos de onda**, `position:absolute; inset:0`, borde de 1 px del color de estado, `border-radius:50%`, cada uno con la animación `pxaOnda` de 3 s en bucle y desfases de **0 s, 1 s y 2 s** (así siempre hay una onda en vuelo).
2. **Un anillo exterior estático**, igual pero sin animación y con `opacity:.32` — es el borde de reposo del indicador.
3. **Anillo interior** de 26 px, borde de 1 px del color de estado.
4. **Punto central** de 7 px relleno del color de estado.

El color es el mismo token de estado que ya usa el semáforo (verde `#0F7B0F` claro / `#6CCB5F` oscuro; ámbar `#9D5D00` / `#FCE100`; rojo `#C42B1C` / `#FF99A4`), heredado por variable CSS, de modo que las ondas cambian de color con el estado sin tocar la animación.

## Keyframes

```css
@keyframes pxaOnda {
  0%   { transform: scale(.16); opacity: .7 }
  70%  { opacity: .14 }
  100% { transform: scale(1);  opacity: 0 }
}
```

`scale(.16)` sobre 44 px arranca la onda en ~7 px, es decir exactamente en el borde del punto central. Curva de tiempo: `cubic-bezier(.22,.61,.36,1)` (rápida al salir, frenada al final).

## HTML/CSS de referencia
`--e` es el color de estado; en el prototipo se fija en el contenedor de la sección de estado.

```html
<div style="width:44px;height:44px;position:relative;display:flex;align-items:center;justify-content:center">
  <div style="position:absolute;inset:0;border:1px solid var(--e);border-radius:50%;animation:pxaOnda 3s cubic-bezier(.22,.61,.36,1) infinite"></div>
  <div style="position:absolute;inset:0;border:1px solid var(--e);border-radius:50%;animation:pxaOnda 3s cubic-bezier(.22,.61,.36,1) 1s infinite"></div>
  <div style="position:absolute;inset:0;border:1px solid var(--e);border-radius:50%;animation:pxaOnda 3s cubic-bezier(.22,.61,.36,1) 2s infinite"></div>
  <div style="position:absolute;inset:0;border:1px solid var(--e);border-radius:50%;opacity:.32"></div>
  <div style="width:26px;height:26px;border:1px solid var(--e);border-radius:50%;display:flex;align-items:center;justify-content:center">
    <div style="width:7px;height:7px;border-radius:50%;background:var(--e)"></div>
  </div>
</div>
```

## Notas de implementación en Streamlit
- Es CSS puro: va en el bloque de estilos inyectado (`app/estilos.css` cargado con `st.markdown(..., unsafe_allow_html=True)`), y el indicador se pinta como HTML propio dentro de `st.sidebar`, no con `st.markdown(f"### {emoji} …")`.
- El HTML se regenera en cada `st.rerun()`, así que la animación se reinicia en cada interacción. Es aceptable porque el ciclo es corto y continuo; no intentes preservar la fase.
- Respeta la preferencia del sistema:

```css
@media (prefers-reduced-motion: reduce) {
  /* sin ondas: solo el anillo estático y el punto */
  .pxa-onda { animation: none; opacity: 0 }
}
```

- No añadas la animación a ningún otro elemento. En esta interfaz solo se mueven dos cosas: estas ondas y los tres puntos del estado "pensando".
