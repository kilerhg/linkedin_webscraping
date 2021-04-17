__author__ = "kilerhg"
# Link: https://github.com/kilerhg

import csv
from time import sleep
from selenium import webdriver
from parsel import Selector
from selenium.webdriver import Chrome

def SalvarCsv(nome,titulo,empresa,escola,link,nome_arquivo='base'):
    try:
        f = open(f"{nome_arquivo}.csv") # Verifica Existencia
        with open(f'{nome_arquivo}.csv','a+', encoding='utf-8') as arquivo: # Define Atalho como arquivo
            arquivo.write(f'"{nome}";"{titulo}";"{empresa}";"{escola}";"{link}"\n') # Salva Dados Sobrepondo

    except IOError: # Caso não exista arquivo cai nesta exeção
        with open(f'{nome_arquivo}.csv','w+', encoding='utf-8') as arquivo:
            arquivo.write('nome;titulo;empresa;escola;link\n') # Salva Cabeçalho
            arquivo.write(f'"{nome}";"{titulo}";"{empresa}";"{escola}";"{link}"\n') # Salva Dados concatenando

    arquivo.close() # Fecha arquivo

# aqui é feita a exigência das urls dos perfis
# input_url = str(input('urls: ')) # aqui é feita a requisição dos urls
# linkedin_url = input_url.split("https://") # aqui é feita a divisão dos urls pelo https
# linkedin_url.remove(lista_url[0]) # o primeiro item da lista fica vazio e por isso o tirei
linkedin_urls =  ['https://www.linkedin.com/in/andr%C3%A9-felipe-guisasola-antunes-9a0490173/','https://www.linkedin.com/in/lucasnunesdeassis/',
'https://www.linkedin.com/in/yan-liao-amorelli-0566b6175/',
'https://www.linkedin.com/in/rabelonms/',
'https://www.linkedin.com/in/jonathanpauluze/',
'https://www.linkedin.com/in/ivoneijr/',
'https://www.linkedin.com/in/danilo-carlos-pereira-da-silva-617377184/'] #url de teste
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
for linkedin_url in linkedin_urls:
    driver.get(linkedin_url) # o perfil da pessoa é acessado
    sleep(5) # tempo de espera de 5 segundos
    sel = Selector(text=driver.page_source) # coleta-se o código fonte da página daquele perfil
    name = sel.xpath('//div[@class="flex-1 mr5 pv-top-card__list-container"]/ul/li/text()').extract_first() # Coleta Nome

    # Limpa Variável name
    if name:
        name = name.strip() # Tira Espaços Vazios Antes e depois
    else:
        name = 'Nome não encontrado' # caso de erro retorna para Variável

    job_title = sel.xpath('//div[@class="flex-1 mr5 pv-top-card__list-container"]/h2/text()').extract_first() # Coleta Titulo

    # Limpa Variável Titulo
    if job_title:
        job_title = job_title.strip() # Tira Espaços Vazios Antes e depois
    else:
        job_title = 'Trabalho não encontrado' # caso de erro retorna para Variável

    company_college = sel.xpath('//ul[@class="pv-top-card--experience-list"]/li/a/span/text()').getall() # Coleta Escola & Empresa

    # Limpa Variável Escola & Empresa
    if len(company_college) > 1:
        # Caso a pessoa tenha trabalho puxa ambos
        company = company_college[0] # Separando Variaveis
        college = company_college[1] # Separando Variaveis
    else:
        # Caso a pessoa não tenha trabalho puxa somente Escola
        company = '' # Deixa Variável vazia
        college = company_college[0] # Separando Variaveis

    if company:
        company = company.strip() # Tira Espaços Vazios Antes e depois
    else:
        company = 'Empresa não encontrada' # caso de erro retorna para Variável

    if college:
        college = college.strip() # Tira Espaços Vazios Antes e depois
    else:
        college = 'Acadêmico não encontrado' # caso de erro retorna para Variável

    faculdades = vit.xpath('//h3[@class="pv-entity__school-name t-16 t-black t-bold"]/text()').getall()


    ano = vit.xpath('//p[@class="pv-entity__dates t-14 t-black--light t-normal"]/span[2]/time/text()').getall()
    
    # dando prioridade para arvore

    #arvore = sel.xpath('//li[@class="pv-entity__position-group-pager pv-profile-section__list-item ember-view"]/section/ul').extract_first()

    arvore = vit.xpath('//ul[@class="pv-profile-section__section-info section-info pv-profile-section__section-info--has-no-more"]/li[1]/section/ul').extract_first()
    if arvore:
        cargo = vit.xpath('//li[@class="pv-entity__position-group-pager pv-profile-section__list-item ember-view"]/section/ul/li[1]/div/div/div/div/div/div/h3/span[2]/text()').extract_first()
        empresa_cargo = vit.xpath('//li[@class="pv-entity__position-group-pager pv-profile-section__list-item ember-view"]/section/div/a/div/div[2]/h3/span[2]/text()').extract_first()
    else:
        cargo = vit.xpath('//li[@class="pv-entity__position-group-pager pv-profile-section__list-item ember-view"]/section/div/div[1]/a/div[2]/h3/text()').extract_first()
        empresa_cargo = vit.xpath('//li[@class="pv-entity__position-group-pager pv-profile-section__list-item ember-view"]/section/div/div/a/div[2]/p[2]/text()').extract_first()

    linkedin_url = driver.current_url # Pegando Link do Perfil Atual

    find
    
    if 'Universidade Estadual de Campinas' in faculdades:
        print('teste')

    print(f'''
    ---------------------------------------------
    Nome: {name}
    Empresa: {empresa_cargo}
    Faculdade: {college}

    ---------------------------------------------
    ''')

    # SalvarCsv(name,job_title,company,college,linkedin_url) # Executando Função para salvar os dados
driver.quit() # fecha-se o driver
