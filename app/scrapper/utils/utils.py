import requests
import speedtest

def checar_conexao():
    try:
        requests.get("https://google.com/")
    except requests.exceptions.ConnectionError:
        erro = sys.stderr
        erro.write("Você não esta conectado a internet.")

def VelocidadeInternet(mostrar=True,retornar=True):
    velocidade = speedtest.Speedtest()

    download = round(velocidade.download()/1000000,2)
    upload = round(velocidade.upload()/1000000,2)
    if mostrar:
        print(f"Velocidade de Download em Mbps: {download}")
        print(f"Velocidade de Upload   em Mbps: {upload}")
    
    if retornar:
        return download, upload
    

class FileHandling:
    ...


class CsvHandling(FileHandling):
    ...