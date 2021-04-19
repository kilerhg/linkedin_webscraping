def VelocidadeInternet(mostrar=True,retornar=True):
    import speedtest

    velocidade = speedtest.Speedtest()

    download = round(velocidade.download()/1000000,2)
    upload = round(velocidade.upload()/1000000,2)
    if mostrar:
        print(f"Velocidade de Download em Mbps: {download}")
        print(f"Velocidade de Upload   em Mbps: {upload}")
    
    if retornar:
        return download, upload


VelocidadeInternet()




