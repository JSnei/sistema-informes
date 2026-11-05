const sapTicket = document.getElementById('sap_tienda');
const datosTienda = document.getElementById('datos-tienda');
const guardarTicket = document.getElementById('guardar-ticket');
let consultaTienda = 0;
let esperaTienda;
let sapVerificado = '';

async function buscarTienda() {
    const consulta = ++consultaTienda;
    const sap = sapTicket.value.trim();
    guardarTicket.disabled = true;
    sapVerificado = '';
    if (!sap) {
        datosTienda.textContent = 'Ingresa el SAP para completar los datos de la tienda.';
        return;
    }
    datosTienda.textContent = 'Buscando tienda…';
    try {
        const respuesta = await fetch('/admin/tickets/tienda?' + new URLSearchParams({sap}));
        if (respuesta.redirected) throw new Error('La sesión terminó. Ingresa nuevamente.');
        const tienda = await respuesta.json();
        if (consulta !== consultaTienda || sapTicket.value.trim() !== sap) return;
        if (!respuesta.ok) throw new Error(tienda.error);
        datosTienda.textContent = `Tienda: ${tienda.nombre} — ${tienda.sap}\nDirección: ${tienda.direccion || 'No registrada'}\nCiudad: ${tienda.ciudad || 'No registrada'}`;
        sapVerificado = sap;
        guardarTicket.disabled = false;
    } catch (error) {
        if (consulta === consultaTienda) datosTienda.textContent = error.message || 'No se pudo consultar la tienda.';
    }
}

sapTicket.addEventListener('input', () => {
    ++consultaTienda;
    sapVerificado = '';
    guardarTicket.disabled = true;
    datosTienda.textContent = 'Buscando tienda…';
    clearTimeout(esperaTienda);
    esperaTienda = setTimeout(buscarTienda, 350);
});
document.getElementById('registro-ticket').addEventListener('submit', (evento) => {
    if (!sapVerificado || sapVerificado !== sapTicket.value.trim()) {
        evento.preventDefault();
        buscarTienda();
    }
});
if (sapTicket.value) buscarTienda();

const buscarTicket = document.getElementById('buscar-ticket');
const filtroEstado = document.getElementById('filtro-estado');
const filtroNumero = document.getElementById('filtro-numero');
function filtrarTickets() {
    let visibles = 0;
    document.querySelectorAll('.solicitud').forEach((solicitud) => {
        solicitud.hidden = !(solicitud.textContent.toLocaleLowerCase().includes(buscarTicket.value.trim().toLocaleLowerCase()) &&
            (!filtroEstado.value || solicitud.dataset.estado === filtroEstado.value) &&
            (!filtroNumero.value || solicitud.dataset.numero === filtroNumero.value));
        if (!solicitud.hidden) visibles++;
    });
    document.getElementById('sin-resultados').hidden = visibles > 0;
}
buscarTicket.addEventListener('input', filtrarTickets);
filtroEstado.addEventListener('change', filtrarTickets);
filtroNumero.addEventListener('change', filtrarTickets);

document.querySelectorAll('.copiar-enlace-ticket').forEach((boton) => {
    boton.addEventListener('click', async () => {
        const campo = document.getElementById(boton.dataset.campo);
        const resultado = boton.nextElementSibling;
        try {
            await navigator.clipboard.writeText(campo.value);
            resultado.textContent = 'Enlace copiado.';
        } catch {
            campo.select();
            resultado.textContent = 'Selecciona el enlace y cópialo manualmente.';
        }
    });
});

document.querySelectorAll('.eliminar-ticket').forEach((formulario) => {
    formulario.addEventListener('submit', (evento) => {
        if (!window.confirm('¿Eliminar este ticket? Se desactivará su enlace pendiente. Los informes existentes se conservarán. Esta acción no se puede deshacer.')) {
            evento.preventDefault();
        }
    });
});
