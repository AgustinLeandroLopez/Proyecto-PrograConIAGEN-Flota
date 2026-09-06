vehiculos = [
    {"id": 1, "patente": "ABC123", "velocidad": 0, "minutos_detenido": 45},
    {"id": 2, "patente": "DEF456", "velocidad": 0, "minutos_detenido": 15},
    {"id": 3, "patente": "GHI789", "velocidad": 60, "minutos_detenido": 0},
]

for vehiculo in vehiculos:
    print(f"Vehiculo {vehiculo['id']} - Patente: {vehiculo['patente']}")
    print(f"Velocidad: {vehiculo['velocidad']} km/h")
    print(f"Minutos detenido: {vehiculo['minutos_detenido']}")

    if vehiculo["velocidad"] == 0:
        if vehiculo["minutos_detenido"] > 30:
            print("ALERTA: El vehiculo lleva demasiado tiempo detenido.")
        else:
            print("El vehiculo esta detenido, pero dentro del tiempo permitido.")
    else:
        print("El vehiculo esta en movimiento.")

    print()
