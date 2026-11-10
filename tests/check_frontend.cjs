// Ejecución: node tests/check_frontend.cjs. No requiere navegador ni red.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

function elemento(dataset = {}) {
    return {dataset, value:'', textContent:'', hidden:false, selectionStart:0, handlers:{}, validationMessage:'',
        addEventListener(nombre, fn) { this.handlers[nombre] = fn; },
        setCustomValidity(mensaje) { this.validationMessage = mensaje; },
        reportValidity() { return !this.validationMessage && !!this.value; },
        setSelectionRange(a) { this.selectionStart = a; }};
}
const entrada = elemento({valor:''});
const oculto = elemento();
const formulario = elemento();
formulario.querySelector = selector => selector === '.precio-formateado' ? entrada : oculto;
const ids = {};
const contexto = {document:{
    getElementById(id) { return ids[id] ||= elemento(); },
    querySelectorAll(selector) { return selector === '.formulario-precio' ? [formulario] : []; }
}, setTimeout, clearTimeout};
const codigo = fs.readFileSync(path.join(__dirname, '../static/js/tickets_oficina.js'), 'utf8');
vm.runInNewContext(codigo, contexto);
for (const [escrito, mostrado, guardado] of [
    ['100', '100', '100'], ['1000', '1.000', '1000'],
    ['1000000', "1'000.000", '1000000'],
    ["1'000.000,50", "1'000.000,50", '1000000.50'],
    ['0', '0', '0'], ['9999999999,99', "9.999'999.999,99", '9999999999.99']
]) {
    entrada.value = escrito;
    entrada.selectionStart = escrito.length;
    entrada.handlers.input();
    assert.equal(entrada.value, mostrado);
    assert.equal(oculto.value, guardado);
    assert.equal(entrada.validationMessage, '');
}
for (const escrito of ['-1', 'NaN', '10000000000', '1,001']) {
    entrada.value = escrito;
    entrada.selectionStart = escrito.length;
    entrada.handlers.input();
    assert.ok(entrada.validationMessage);
    assert.equal(oculto.value, '');
}
const tecnico = fs.readFileSync(path.join(__dirname, '../static/js/ticket_servicio.js'), 'utf8');
new vm.Script(tecnico);
module.exports = {resultado:'OK', casosPrecios:10, scriptsVerificados:2};
if (require.main === module) console.log(JSON.stringify(module.exports));
