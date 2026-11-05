const formularioServicio = document.getElementById('formulario-servicio');
const valoresServicio = JSON.parse(document.getElementById('valores-servicio').textContent);

// El ticket y la tienda vienen del enlace; solo se restauran los datos del tecnico.
for (const [nombre, valor] of Object.entries(valoresServicio)) {
    if (['ticket', 'sap_tienda', 'ticket_solicitud_id'].includes(nombre)) continue;
    const campo = formularioServicio.elements.namedItem(nombre);
    if (campo && valor !== null) campo.value = valor;
}
mostrarOtroServicio();
