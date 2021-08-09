__author__ = "kilerhg"

# Link: https://github.com/kilerhg


import csv
import sys
from time import sleep

import requests
from parsel import Selector
from selenium.webdriver import Chrome
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


class Xpaths:
    tag_x = '//section[@class="pv-profile-section pv-profile-section--reorder-enabled background-section artdeco-card mt4 ember-view"]'
    name = '//div[@class="flex-1 mr5 pv-top-card__list-container"]/ul/li/text()'
    job_title = '//div[@class="flex-1 mr5 pv-top-card__list-container"]/h2/text()'
    faculdades = '//h3[@class="pv-entity__school-name t-16 t-black t-bold"]/text()'
    ano = '//p[@class="pv-entity__dates t-14 t-black--light t-normal"]/span[2]/time/text()'
    arvore = '//ul[@class="pv-profile-section__section-info section-info pv-profile-section__section-info--has-no-more"]/li[1]/section/ul'
    cargo_arvore = '//li[@class="pv-entity__position-group-pager pv-profile-section__list-item ember-view"]/section/ul/li[1]/div/div/div/div/div/div/h3/span[2]/text()'
    cargo = '//li[@class="pv-entity__position-group-pager pv-profile-section__list-item ember-view"]/section/div/div[1]/a/div[2]/h3/text()'
    empresa_cargo_arvore = '//li[@class="pv-entity__position-group-pager pv-profile-section__list-item ember-view"]/section/div/a/div/div[2]/h3/span[2]/text()'
    empresa_cargo = '//li[@class="pv-entity__position-group-pager pv-profile-section__list-item ember-view"]/section/div/div/a/div[2]/p[2]/text()'
    curso_atual = '//p[@class="pv-entity__secondary-title pv-entity__fos t-14 t-black t-normal"]/span[2]/text()'


def checar_conexao():
    try:
        requests.get("https://google.com/")
    except requests.exceptions.ConnectionError:
        erro = sys.stderr
        erro.write("Você não esta conectado a internet.")


def salvar_csv(nome, empresa, cargo, aluno, curso, ano_inicio, ano_termino, link_url_linkedin, nome_arquivo='base'):
    """
        Função para a escrita e criação do arvquivo CSV.

        :param nome_arquivo: nome do arquivo.
        :param nome: nome da pessoa.
        :param empresa: nome da impresa.
        :param cargo: nome do cargo.
        :param aluno: nome do aluno.
        :param curso: nome do curso.
        :param ano_inicio: ano de entrada.
        :param ano_termino: ano de saida.
        :param link_url_linkedin: link do perfil.
    """
    try:
        with open(f'{nome_arquivo}.csv', 'a', encoding='utf-8') as arquivo:
            arq = csv.writer()
            arq.writerow(f'"{nome}",'
                         f'"{empresa}",'
                         f'"{cargo}",'
                         f'"{aluno}",'
                         f'"{curso}",'
                         f'"{ano_inicio}",'
                         f'"{ano_termino}",'
                         f'"{link_url_linkedin}"')  # Salva Dados Sobrepondo

    except IOError:  # Caso não exista arquivo cai nesta exeção
        with open(f'{nome_arquivo}.csv', 'w+', encoding='utf-8') as arquivo:
            arq = csv.writer(arquivo)
            arq.writerow('nome,cargo,empresa,aluno_unicamp,curso,ingresso,egresso,link')
            arq.writerow(f'"{nome}",'
                         f'"{empresa}",'
                         f'"{cargo}",'
                         f'"{aluno}",'
                         f'"{curso}",'
                         f'"{ano_inicio}",'
                         f'"{ano_termino}",'
                         f'"{link_url_linkedin}"')


def limpador(dados):
    dados = str(dados)
    final = []
    links = dados.split('https://')
    for link in links:
        final.append('https://' + link)

    return final[1:]


checar_conexao()
dados_sujos = str(input('Digite os links de forma linear: ')).strip()

velocidade_internet = 2  # Segue a tabela Abaixo para Medir
# Muito Boa : 0.5 # Recomendado Começar Por aqui, se der problema vai aumentando
# Boa       : 2
# Moderada  : 5
# Ruim      : 7
# Muito Ruim: 10

linkedin_urls = limpador(dados_sujos)  # Limpeza e rebecimentos das varias URLS

# entrada de login e senha do usuario
usuario = input('Digite usuario: ')
senha = input('Digite senha: ')

driver = Chrome()
driver.get('https://www.linkedin.com')

username = driver.find_element_by_id('session_key')
username.send_keys(f'{usuario}')

# dormida de 0.5 segundos
sleep(1.0)

password = driver.find_element_by_id('session_password')
password.send_keys(f'{senha}')

# dormida de 1 segundo
sleep(1.0)

log_in_button = driver.find_element_by_class_name('sign-in-form__submit-button')
log_in_button.click()

########## DENTRO DO LINKEDIN ##########

driver.maximize_window()  # Coloca em Tela Cheia, com finalidade de deixar a tela em foco
# try:
for linkedin_url in linkedin_urls:
    driver.get(linkedin_url)  # o perfil da pessoa é acessado
    print(linkedin_url)
    sleep(velocidade_internet)
    WebDriverWait(driver, 30).until(
        EC.presence_of_element_located((By.XPATH, Xpaths.tag_x)))  # Aguarda para continuar enquanto tag x não carregar
    sel = Selector(text=driver.page_source)  # coleta-se o código fonte da página daquele perfil
    name = sel.xpath(Xpaths.name).extract_first()  # Coleta Nome

    # Limpa Variável name
    if name:
        name = name.strip()  # Tira Espaços Vazios Antes e depois
    else:
        name = 'Nome não encontrado'  # caso de erro retorna para Variável

    job_title = sel.xpath(Xpaths.job_title).extract_first()  # Coleta Titulo

    faculdades = sel.xpath(Xpaths.faculdades).getall()

    ano = sel.xpath(Xpaths.ano).getall()

    # dando prioridade para arvore

    arvore = sel.xpath(Xpaths.arvore).extract_first()
    if arvore:
        cargo = sel.xpath(Xpaths.cargo_arvore).extract_first()
        empresa_cargo = sel.xpath(Xpaths.empresa_cargo_arvore).extract_first()
    else:
        cargo = sel.xpath(Xpaths.cargo).extract_first()
        empresa_cargo = sel.xpath(Xpaths.empresa_cargo).extract_first()

    faculdades = sel.xpath(Xpaths.faculdades).getall()
    ano = sel.xpath(Xpaths.ano).getall()
    curso_atual = sel.xpath(Xpaths.curso_atual).getall()

    faculdades = [item.lower() for item in faculdades]

    for posfaculdade, faculdade in enumerate(faculdades):
        if len(faculdade) > 32:
            faculdades[posfaculdade] = faculdade[:33]
            # print(faculdade)

    if 'Universidade Estadual de Campinas'.lower() in faculdades:
        valor_index = faculdades.index('Universidade Estadual de Campinas'.lower())
        a = valor_index * 2
        ano_inicio, ano_termino = ano[a:a + 2]
        aluno = 'sim'
        if valor_index == 0:
            curso_atual = curso_atual[valor_index]
        else:
            curso_atual = curso_atual[0]

    else:
        ano_inicio = ano_termino = curso_atual = '---'
        aluno = 'nao'

    if cargo:
        cargo = cargo.strip()
    else:
        cargo = 'não encontrado'

    if empresa_cargo:
        empresa_cargo = empresa_cargo.strip()
    else:
        empresa_cargo = 'não encontrado'

    if aluno:
        aluno = aluno.strip()
    else:
        aluno = 'não encontrado'

    if curso_atual:
        curso_atual = curso_atual.strip()
    else:
        curso_atual = 'curso_atual não encontrado'

    if ano_inicio:
        ano_inicio = ano_inicio.strip()
    else:
        ano_inicio = 'não encontrado'

    if ano_termino:
        ano_termino = ano_termino.strip()
    else:
        ano_termino = 'não encontrado'

    linkedin_url = driver.current_url  # Pegando Link do Perfil Atual
    salvar_csv(name, cargo, empresa_cargo, aluno, curso_atual, ano_inicio, ano_termino,
               linkedin_url.strip())
# except :
#    print('Erro')
#    driver.quit() # fecha-se o driver
driver.quit()
