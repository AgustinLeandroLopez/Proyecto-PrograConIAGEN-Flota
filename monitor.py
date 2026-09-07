LIMITE_MINUTOS_DETENIDO = 30


def esta_esperando_viaje(vehiculo):
    return bool(vehiculo.get("esperando_viaje", False)) and vehiculo["velocidad"] == 0


def normalizar_esperando_viaje(velocidad, esperando_viaje):
    """Un vehículo en movimiento no puede permanecer esperando viaje."""
    return bool(esperando_viaje) and velocidad == 0


def esta_en_alerta(vehiculo):
    return (
        not esta_esperando_viaje(vehiculo)
        and
        vehiculo["velocidad"] == 0
        and vehiculo["minutos_detenido"] > LIMITE_MINUTOS_DETENIDO
    )


def obtener_estado(vehiculo):
    if esta_esperando_viaje(vehiculo):
        return "El vehiculo esta esperando viaje."

    if esta_en_alerta(vehiculo):
        return "ALERTA: El vehiculo lleva demasiado tiempo detenido."

    if vehiculo["velocidad"] == 0:
        return "El vehiculo esta detenido, pero dentro del tiempo permitido."

    return "El vehiculo esta en movimiento."


def obtener_alertas(vehiculos):
    return [vehiculo for vehiculo in vehiculos if esta_en_alerta(vehiculo)]


def mostrar_estado_vehiculo(vehiculo):
    print(f"Vehiculo {vehiculo['id']} - Patente: {vehiculo['patente']}")
    print(f"Velocidad: {vehiculo['velocidad']:g} km/h")
    print(f"Minutos detenido: {vehiculo['minutos_detenido']}")
    print(f"Esperando viaje: {'Si' if vehiculo['esperando_viaje'] else 'No'}")
    print(obtener_estado(vehiculo))
    print()
