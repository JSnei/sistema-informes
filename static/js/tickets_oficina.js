function formatearPrecio(valor) {
    const [entero, decimales] = valor.split(',');
    const grupos = (entero || '0').replace(/^0+(?=\d)/, '').match(/\d{1,3}(?=(\d{3})*$)/g);
    const agrupado = grupos.map((grupo, indice) => {
        if (indice === 0) return grupo;
        return ((grupos.length - indice) % 2 === 0 ? "'" : '.') + grupo;
    }).join('');
    return agrupado + (decimales !== undefined ? ',' + decimales : '');
}

document.querySelectorAll('.formulario-precio').forEach((formulario) => {
    const campo = formulario.querySelector('.precio-formateado');
    const valorGuardado = formulario.querySelector('.precio-valor');
    function actualizarPrecio(conservarCursor = true) {
        const posicion = campo.selectionStart ?? campo.value.length;
        const caracteresAntes = campo.value.slice(0, posicion).replace(/[^0-9,]/g, '').length;
        const valor = campo.value.replace(/[.'\s]/g, '');
        campo.setCustomValidity('');
        valorGuardado.value = '';
        if (!valor) return;
        if (!/^\d+(,\d{0,2})?$/.test(valor) || Number(valor.replace(',', '.')) > 9999999999.99) {
            campo.setCustomValidity('Ingresa un precio entre 0 y 9.999\'999.999,99, con máximo dos decimales separados por coma.');
            return;
        }
        valorGuardado.value = valor.replace(',', '.');
        campo.value = formatearPrecio(valor);
        if (conservarCursor) {
            let cursor = 0;
            let contados = 0;
            while (cursor < campo.value.length && contados < caracteresAntes) {
                if (/[0-9,]/.test(campo.value[cursor])) contados++;
                cursor++;
            }
            campo.setSelectionRange(cursor, cursor);
        }
    }
    campo.value = campo.dataset.valor.replace('.', ',');
    actualizarPrecio(false);
    campo.addEventListener('input', () => actualizarPrecio());
    formulario.addEventListener('submit', (evento) => {
        actualizarPrecio(false);
        if (!campo.reportValidity() || !valorGuardado.value) evento.preventDefault();
    });
});

document.querySelectorAll('[data-precio-texto]').forEach((texto) => {
    texto.textContent = formatearPrecio(texto.dataset.precioTexto.replace('.', ','));
});

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
function filtrarTickets() {
    let visibles = 0;
    document.querySelectorAll('.solicitud').forEach((solicitud) => {
        solicitud.hidden = !solicitud.textContent.toLocaleLowerCase().includes(buscarTicket.value.trim().toLocaleLowerCase());
        if (!solicitud.hidden) visibles++;
    });
    document.getElementById('sin-resultados').hidden = visibles > 0;
}
buscarTicket.addEventListener('input', filtrarTickets);
filtrarTickets();

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
