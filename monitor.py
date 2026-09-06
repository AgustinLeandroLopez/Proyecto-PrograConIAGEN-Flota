LIMITE_MINUTOS_DETENIDO = 30


def esta_en_alerta(vehiculo):
    return (
        vehiculo["velocidad"] == 0
        and vehiculo["minutos_detenido"] > LIMITE_MINUTOS_DETENIDO
    )


def obtener_estado(vehiculo):
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
    print(obtener_estado(vehiculo))
    print()
