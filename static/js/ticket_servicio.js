const formularioServicio = document.getElementById('formulario-servicio');
const valoresServicio = JSON.parse(document.getElementById('valores-servicio').textContent);

// El ticket y la tienda vienen del enlace; solo se restauran los datos del tecnico.
for (const [nombre, valor] of Object.entries(valoresServicio)) {
    if (['ticket', 'sap_tienda', 'ticket_solicitud_id'].includes(nombre)) continue;
    const campo = formularioServicio.elements.namedItem(nombre);
    if (campo && valor !== null) campo.value = valor;
}
mostrarOtroServicio();

const fotosEvidencia = document.getElementById('fotos-evidencia');
const estadoFotos = document.getElementById('estado-fotos');
fotosEvidencia.addEventListener('change', () => {
    const cantidad = fotosEvidencia.files.length;
    const faltantes = 4 - cantidad;
    const mensaje = cantidad > 0 && faltantes > 0 ? `Selecciona ${faltantes} ${faltantes === 1 ? 'archivo más' : 'archivos más'}.` : '';
    fotosEvidencia.setCustomValidity(mensaje);
    estadoFotos.textContent = cantidad ? `${cantidad} ${cantidad === 1 ? 'archivo seleccionado' : 'archivos seleccionados'}. ${mensaje}` : '';
});

const fotosTicket = document.getElementById('fotos-ticket');
fotosTicket.addEventListener('change', () => {
    const cantidad = fotosTicket.files.length;
    document.getElementById('estado-ticket').textContent = cantidad ? `${cantidad} ${cantidad === 1 ? 'foto seleccionada' : 'fotos seleccionadas'}.` : '';
});

document.querySelectorAll('.zona-archivos').forEach((zona) => {
    const entrada = document.getElementById(zona.dataset.entrada);
    const lista = zona.querySelector('.lista-adjuntos');

    entrada.addEventListener('change', () => {
        lista.replaceChildren();
        Array.from(entrada.files).forEach((archivo, indice) => {
            const elemento = document.createElement('li');
            const nombre = document.createElement('span');
            nombre.textContent = archivo.name;
            const quitar = document.createElement('button');
            quitar.type = 'button';
            quitar.textContent = 'Quitar';
            quitar.setAttribute('aria-label', `Quitar ${archivo.name}`);
            quitar.addEventListener('click', () => {
                const seleccion = new DataTransfer();
                Array.from(entrada.files).forEach((actual, posicion) => {
                    if (posicion !== indice) seleccion.items.add(actual);
                });
                entrada.files = seleccion.files;
                entrada.dispatchEvent(new Event('change', {bubbles: true}));
            });
            elemento.append(nombre, quitar);
            lista.append(elemento);
        });
        lista.hidden = entrada.files.length === 0;
    });

    zona.addEventListener('dragover', (evento) => {
        evento.preventDefault();
        evento.dataTransfer.dropEffect = 'copy';
        zona.classList.add('arrastrando');
    });

    zona.addEventListener('dragleave', (evento) => {
        if (!zona.contains(evento.relatedTarget)) zona.classList.remove('arrastrando');
    });

    zona.addEventListener('drop', (evento) => {
        evento.preventDefault();
        evento.stopPropagation();
        zona.classList.remove('arrastrando');
        const nuevos = Array.from(evento.dataTransfer.files);
        if (!nuevos.length) return;

        const seleccion = new DataTransfer();
        const incluidos = new Set();
        for (const archivo of [...entrada.files, ...nuevos]) {
            const clave = JSON.stringify([archivo.name, archivo.size, archivo.lastModified, archivo.type]);
            if (!incluidos.has(clave)) {
                seleccion.items.add(archivo);
                incluidos.add(clave);
            }
        }
        entrada.files = seleccion.files;
        entrada.dispatchEvent(new Event('change', {bubbles: true}));
    });
});
