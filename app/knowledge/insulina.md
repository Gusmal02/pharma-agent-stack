# Protocolo de Gestión: Insulina

## 1. Descripción
La insulina es un medicamento de alta sensibilidad térmica (cadena de frío). Su gestión requiere un control estricto de inventario en la base de datos `pharma.db`. Es producida por el páncreas de forma natural; en pacientes diabéticos se administra de forma externa para regular los niveles de glucosa en sangre.

## 2. Requisitos de Venta
- **Receta Médica:** Indispensable (Controlada).
- **Verificación:** Debe validarse el folio contra el sistema de recetas digitales antes de cualquier despacho.

## 3. Almacenamiento y Cadena de Frío
Esta sección es crítica para garantizar la eficacia del medicamento.

- **Insulina sin abrir (frasco o pluma nueva):** Debe conservarse en refrigeración entre 2°C y 8°C. No debe congelarse bajo ninguna circunstancia; un frasco congelado debe desecharse.
- **Insulina en uso (frasco o pluma abierta):** Una vez abierta, puede mantenerse a temperatura ambiente entre 15°C y 30°C por un máximo de 28 días. Después de ese periodo debe desecharse aunque quede producto.
- **Guardar en casa:** Mantener el frasco sin abrir en el refrigerador, en la puerta (zona menos fría). El frasco en uso puede quedarse fuera del refrigerador en un lugar fresco y oscuro, alejado de ventanas y fuentes de calor.
- **Evitar:** Luz solar directa, fuentes de calor como radiadores o tableros de auto, y temperaturas superiores a 37°C. El calor excesivo destruye la proteína de insulina y la vuelve ineficaz.
- **Verificación visual antes de usar:** La insulina debe verse transparente e incolora. Si se observa turbiedad, partículas o coloración amarillenta, desechar el frasco inmediatamente.

## 4. Dosis y Administración
- La dosis es estrictamente individualizada y determinada por el médico tratante. No modificar sin indicación médica.
- **Vías de administración:** Subcutánea (SC) mediante jeringa de insulina, pluma de insulina o bomba de infusión continua.
- **Zonas de inyección recomendadas:** Abdomen (absorción más rápida), muslos, glúteos y parte posterior del brazo. Rotar las zonas para evitar lipodistrofia.

## 5. Contraindicaciones y Advertencias
- **Hipoglucemia:** El efecto adverso más común y peligroso. Síntomas: temblor, sudoración, confusión, pérdida de conciencia. Tratar con 15g de carbohidratos de absorción rápida.
- **Contraindicado en:** Hipoglucemia activa (nivel de glucosa ya bajo).
- **Interacciones relevantes:** Alcohol (potencia el efecto hipoglucemiante), betabloqueadores (pueden enmascarar síntomas), corticosteroides (elevan la glucosa y pueden requerir ajuste de dosis).

## 6. Manejo Técnico en PharmaBot
- El agente PharmaBot está configurado para denegar la venta si no se presenta un folio válido de receta digital.
- **Stock:** Mantenido en `pharma.db` bajo la categoría "Especialidad".
- **Cadena de frío:** Al momento del despacho, verificar que el empaque esté íntegro y que el producto no haya sido expuesto a temperaturas fuera del rango durante el transporte.
