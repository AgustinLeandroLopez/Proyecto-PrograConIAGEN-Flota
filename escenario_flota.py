"""Distancias ficticias y cálculo de costos desde los datos persistidos."""

ZONAS = ("Centro", "Norte", "Sur", "Oeste")
DISTANCIAS = ((0, 6, 5, 4), (6, 0, 11, 10), (5, 11, 0, 9), (4, 10, 9, 0))
# Valores iniciales para migración y semillas; no se usan para cotizar.
PERFILES = (("Centro", 4000, 3000), ("Norte", 4500, 3400),
            ("Sur", 3500, 2800), ("Oeste", 4200, 3200))
PRECIO_KM_VIAJE = 800
PRECIO_KM_RETIRO = 400
MINIMO_KM = 300
MAX_PRESUPUESTO = 1000000
SOLICITUD_INICIAL = {"origen": "Centro", "destino": "Norte", "presupuesto": 9000}
CONFIGURACION_INICIAL = {"zona": "Centro", "tarifa_base": 4000, "precio_minimo": 3000}


def validar_configuracion(zona, tarifa_base, precio_minimo):
    if zona not in ZONAS:
        raise ValueError("La zona debe ser Centro, Norte, Sur u Oeste.")
    for nombre, valor in (("tarifa base", tarifa_base), ("precio mínimo base", precio_minimo)):
        if type(valor) is not int or not 1 <= valor <= MAX_PRESUPUESTO:
            raise ValueError(f"El valor de {nombre} debe ser un entero de 1 a 1000000 pesos ficticios.")
    if precio_minimo > tarifa_base:
        raise ValueError("El precio mínimo base no puede superar la tarifa base.")


def validar_solicitud(datos=None):
    if datos is None:
        return dict(SOLICITUD_INICIAL)
    if not isinstance(datos, dict) or set(datos) != set(SOLICITUD_INICIAL):
        raise ValueError("Indicá origen, destino y presupuesto del viaje ficticio.")
    if datos["origen"] not in ZONAS or datos["destino"] not in ZONAS:
        raise ValueError("Elegí zonas válidas del escenario ficticio.")
    if datos["origen"] == datos["destino"]:
        raise ValueError("El origen y el destino deben ser distintos.")
    if type(datos["presupuesto"]) is not int or not 1 <= datos["presupuesto"] <= MAX_PRESUPUESTO:
        raise ValueError("El presupuesto debe ser un entero de 1 a 1000000 pesos ficticios.")
    return dict(datos)


def distancia(origen, destino):
    return DISTANCIAS[ZONAS.index(origen)][ZONAS.index(destino)]


def cotizar(vehiculos, solicitud):
    viaje = distancia(solicitud["origen"], solicitud["destino"])
    candidatos = []
    for vehiculo in vehiculos:
        zona, base, piso = (vehiculo[k] for k in ("zona", "tarifa_base", "precio_minimo"))
        validar_configuracion(zona, base, piso)
        retiro = distancia(zona, solicitud["origen"])
        candidatos.append({**vehiculo, "zona": zona, "km_retiro": retiro, "km_viaje": viaje,
                           "tarifa_base": base, "minimo_base": piso,
                           "precio_referencia": base + viaje * PRECIO_KM_VIAJE + retiro * PRECIO_KM_RETIRO,
                           "precio_minimo": piso + (viaje + retiro) * MINIMO_KM})
    return sorted(candidatos, key=lambda v: (v["km_retiro"], v["precio_referencia"], v["id"]))


def catalogo():
    return {"ficticio": True, "zonas": list(ZONAS), "solicitud_inicial": dict(SOLICITUD_INICIAL),
            "max_presupuesto": MAX_PRESUPUESTO,
            "tarifas": {"km_viaje": PRECIO_KM_VIAJE, "km_retiro": PRECIO_KM_RETIRO,
                        "minimo_km_total": MINIMO_KM}}
