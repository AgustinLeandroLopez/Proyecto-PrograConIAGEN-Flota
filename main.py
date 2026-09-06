from database import consultar_vehiculos, inicializar_base_de_datos
from monitor import mostrar_estado_vehiculo


def main():
    inicializar_base_de_datos()
    vehiculos = consultar_vehiculos()

    for vehiculo in vehiculos:
        mostrar_estado_vehiculo(vehiculo)


if __name__ == "__main__":
    main()
