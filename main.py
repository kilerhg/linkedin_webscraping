__author__ = "kilerhg"
# Link: https://github.com/kilerhg

import csv
from time import sleep
from selenium import webdriver
from parsel import Selector
from selenium.webdriver import Chrome
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

def SalvarCsv(nome,empresa,cargo,aluno,curso,ano_inicio,ano_termino,link_url_linkedin,nome_arquivo='base'):
    try:
        f = open(f"{nome_arquivo}.csv") # Verifica Existencia
        with open(f'{nome_arquivo}.csv','a+', encoding='utf-8') as arquivo: # Define Atalho como arquivo
            arquivo.write(f'"{nome}";"{empresa}";"{cargo}";"{aluno}";"{curso}";"{ano_inicio}";"{ano_termino}";"{link_url_linkedin}"\n') # Salva Dados Sobrepondo

    except IOError: # Caso não exista arquivo cai nesta exeção
        with open(f'{nome_arquivo}.csv','w+', encoding='utf-8') as arquivo:
            arquivo.write('nome;cargo;empresa;aluno_unicamp;curso;ingresso;egresso;link\n') # Salva Cabeçalho
            arquivo.write(f'"{nome}";"{empresa}";"{cargo}";"{aluno}";"{curso}";"{ano_inicio}";"{ano_termino}";"{link_url_linkedin}"\n') # Salva Dados Concatenando

    arquivo.close() # Fecha arquivo

def Limpador(dados):
    dados = str(dados)
    final = []
    links = dados.split('https://')
    for link in links:
        final.append('https://'+link)

    return final[1:]

dados_sujos = str(input('Digite os links de forma linear: ')).strip()

velocidade_internet = 2 # Segue a tabela Abaixo para Medir
# Muito Boa : 0.5 # Recomendado Começar Por aqui, se der problema vai aumentando
# Boa       : 2
# Moderada  : 5
# Ruim      : 7
# Muito Ruim: 10

#  aqui é feita a exigência das urls dos perfis
# input_url = str(input('urls: ')) # aqui é feita a requisição dos urls
# linkedin_url = input_url.split("https://") # aqui é feita a divisão dos urls pelo https
# linkedin_url.remove(lista_url[0]) # o primeiro item da lista fica vazio e por isso o tirei
linkedin_urls =  Limpador(dados_sujos) #url de teste
#linkedin_urls = ['https://www.linkedin.com/in/cassiano-de-stefano-110b0b26/', 'https://www.linkedin.com/in/caldeira/', 'https://www.linkedin.com/in/joao-cerqueira/', 'https://www.linkedin.com/in/fabio-affonso-56b06868/', 'https://www.linkedin.com/in/atala/', 'https://www.linkedin.com/in/ronaldo-nascimento-optima/', 'https://www.linkedin.com/in/cristina-schuch-bb0669107/', 'https://www.linkedin.com/in/lidiane-oliveira-1a275922/', 'https://www.linkedin.com/in/neywsouza/', 'https://www.linkedin.com/in/andre-krell-pedro-4011b66/', 'https://www.linkedin.com/in/lidiane-oliveira-1a275922/', 'https://www.linkedin.com/in/lidiane-oliveira-1a275922/']

#for i in range(len(linkedin_url)): # for loop pra completar cada item da lista com o restante que faltava da url
#    url_completa="https://" + linkedin_url[i]
#    linkedin_url_url[i]=url_completa
########## Urls armazenadas ##########


########## Armazenando Usuario e senha ##########
usuario = input('Digite usuario: ')
senha = input('Digite senha: ')
########## Armazenando Usuario e senha ##########



# nessa etapa inicial o webdriver é aberto no diretório abaixo
driver = Chrome()

# nessa etapa é aberto o linkedin via webdriver
driver.get('https://www.linkedin.com')
# encontra a categoria de e-mail

# Achando Campo Usuario
username = driver.find_element_by_id('session_key')

# Enviar Usuario
username.send_keys(f'{usuario}')


# dormida de 0.5 segundos
sleep(1.0)

# encontra categoria de senha
password = driver.find_element_by_id('session_password')

# Enviar Senha
password.send_keys(f'{senha}')

# dormida de 1 segundo
sleep(1.0)

# localiza-se o botão de entrar
log_in_button = driver.find_element_by_class_name('sign-in-form__submit-button')

#clia-se no botão
log_in_button.click()

########## DENTRO DO LINKEDIN ##########
from parsel import Selector
# faz-se o loop de iteração em cada url da lista de url
driver.maximize_window()
#try:
for linkedin_url in linkedin_urls:
    driver.get(linkedin_url) # o perfil da pessoa é acessado
    print(linkedin_url)
    sleep(velocidade_internet)
    element = WebDriverWait(driver, 30).until(
        EC.presence_of_element_located((By.XPATH, '//section[@class="pv-profile-section pv-profile-section--reorder-enabled background-section artdeco-card mt4 ember-view"]'))
        )
    sel = Selector(text=driver.page_source) # coleta-se o código fonte da página daquele perfil
    name = sel.xpath('//div[@class="flex-1 mr5 pv-top-card__list-container"]/ul/li/text()').extract_first() # Coleta Nome

    # Limpa Variável name
    if name:
        name = name.strip() # Tira Espaços Vazios Antes e depois
    else:
        name = 'Nome não encontrado' # caso de erro retorna para Variável

    job_title = sel.xpath('//div[@class="flex-1 mr5 pv-top-card__list-container"]/h2/text()').extract_first() # Coleta Titulo



    faculdades = sel.xpath('//h3[@class="pv-entity__school-name t-16 t-black t-bold"]/text()').getall()

    ano = sel.xpath('//p[@class="pv-entity__dates t-14 t-black--light t-normal"]/span[2]/time/text()').getall()

    # dando prioridade para arvore

    #arvore = sel.xpath('//li[@class="pv-entity__position-group-pager pv-profile-section__list-item ember-view"]/section/ul').extract_first()

    arvore = sel.xpath('//ul[@class="pv-profile-section__section-info section-info pv-profile-section__section-info--has-no-more"]/li[1]/section/ul').extract_first()
    if arvore:
        cargo = sel.xpath('//li[@class="pv-entity__position-group-pager pv-profile-section__list-item ember-view"]/section/ul/li[1]/div/div/div/div/div/div/h3/span[2]/text()').extract_first()
        empresa_cargo = sel.xpath('//li[@class="pv-entity__position-group-pager pv-profile-section__list-item ember-view"]/section/div/a/div/div[2]/h3/span[2]/text()').extract_first()
    else:
        cargo = sel.xpath('//li[@class="pv-entity__position-group-pager pv-profile-section__list-item ember-view"]/section/div/div[1]/a/div[2]/h3/text()').extract_first()
        empresa_cargo = sel.xpath('//li[@class="pv-entity__position-group-pager pv-profile-section__list-item ember-view"]/section/div/div/a/div[2]/p[2]/text()').extract_first()

    faculdades = sel.xpath('//h3[@class="pv-entity__school-name t-16 t-black t-bold"]/text()').getall()
    ano = sel.xpath('//p[@class="pv-entity__dates t-14 t-black--light t-normal"]/span[2]/time/text()').getall()
    curso_atual = sel.xpath('//p[@class="pv-entity__secondary-title pv-entity__fos t-14 t-black t-normal"]/span[2]/text()').getall()

    faculdades = [item.lower() for item in faculdades]

    for posfaculdade, faculdade in enumerate(faculdades):
        if len(faculdade) > 32:
            faculdades[posfaculdade] = faculdade[:33]
            #print(faculdade)


    if 'Universidade Estadual de Campinas'.lower() in faculdades:
        valor_index = faculdades.index('Universidade Estadual de Campinas'.lower())
        a = valor_index * 2
        ano_inicio, ano_termino = ano[a:a+2]
        aluno = 'sim'
        if valor_index == 0:
            curso_atual = curso_atual[valor_index]
        else:
            curso_atual = curso_atual[0]

    else:
        ano_inicio, ano_termino = '---','---'
        curso_atual = '---'
        aluno = 'nao'

    if cargo:
        cargo = cargo.strip() # Tira Espaços Vazios Antes e depois
    else:
        cargo = 'não encontrado' # caso de erro retorna para Variável

    if empresa_cargo:
        empresa_cargo = empresa_cargo.strip() # Tira Espaços Vazios Antes e depois
    else:
        empresa_cargo = 'não encontrado' # caso de erro retorna para Variável

    if aluno:
        aluno = aluno.strip() # Tira Espaços Vazios Antes e depois
    else:
        aluno = 'não encontrado' # caso de erro retorna para Variável

    if curso_atual:
        curso_atual = curso_atual.strip() # Tira Espaços Vazios Antes e depois
    else:
        curso_atual = 'curso_atual não encontrado' # caso de erro retorna para Variável

    if ano_inicio:
        ano_inicio = ano_inicio.strip() # Tira Espaços Vazios Antes e depois
    else:
        ano_inicio = ' não encontrado' # caso de erro retorna para Variável

    if ano_termino:
        ano_termino = ano_termino.strip() # Tira Espaços Vazios Antes e depois
    else:
        ano_termino = ' não encontrado' # caso de erro retorna para Variável


    linkedin_url = driver.current_url # Pegando Link do Perfil Atual
    SalvarCsv(name,cargo,empresa_cargo,aluno,curso_atual,ano_inicio,ano_termino,linkedin_url.strip()) # Executando Função para salvar os dados
#except :
#    print('Erro')
#    driver.quit() # fecha-se o driver
driver.quit() # fecha-se o driver
