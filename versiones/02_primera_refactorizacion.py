# Variable constante que define el limite de minutos que un vehiculo puede estar detenido antes de generar una alerta
LIMITE_MINUTOS_DETENIDO = 30

vehiculos = [
    {"id": 1, "patente": "ABC123", "velocidad": 0, "minutos_detenido": 45},
    {"id": 2, "patente": "DEF456", "velocidad": 0, "minutos_detenido": 15},
    {"id": 3, "patente": "GHI789", "velocidad": 60, "minutos_detenido": 0},
]


# Funcion que determina el estado del vehiculo basado en su velocidad y tiempo detenido
def obtener_estado(vehiculo):
    if vehiculo["velocidad"] == 0 and vehiculo["minutos_detenido"] > LIMITE_MINUTOS_DETENIDO:
        return "ALERTA: El vehiculo lleva demasiado tiempo detenido."
    elif vehiculo["velocidad"] == 0:
        return "El vehiculo esta detenido, pero dentro del tiempo permitido."

    return "El vehiculo esta en movimiento."


# Funcion que muestra el estado del vehiculo
def mostrar_estado_vehiculo(vehiculo):
    print(f"Vehiculo {vehiculo['id']} - Patente: {vehiculo['patente']}")
    print(f"Velocidad: {vehiculo['velocidad']} km/h")
    print(f"Minutos detenido: {vehiculo['minutos_detenido']}")
    print(obtener_estado(vehiculo))
    print()


# Itera sobre la lista de vehiculos y muestra su estado
for vehiculo in vehiculos:
    mostrar_estado_vehiculo(vehiculo)
