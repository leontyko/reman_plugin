# Remote manager plugin
# by Leonty Kopytov @leontyko

import requests
import re
import os
import json

from vacore import VACore

modname = os.path.basename(__file__)[:-3] # calculating modname

# функция на старте
def start(core:VACore):
    manifest = { # возвращаем настройки плагина - словарь
        "name": "reMan", # имя
        "version": "1.0", # версия
        "require_online": False, # требует ли онлайн?
        
        "default_options": {
			"reman_clients" : {
				"ноутбук|ноут|ноутбуке|ноутбуки|ноутбука|ноуте|ноута": { # имена для определения клиента
					"ip": "127.0.0.1", # адрес клиента
					"port": "8000" # порт клиента
				},
			},
            "max_delay": 1440 # максимальное время задержки - 24 часа
        },

        "commands": { # набор скиллов. Фразы скилла разделены | . Если найдены - вызывается функция
            "без звука|выключи звук|со звуком|без мука|включи звук|верни звук": toggle_mute, # команды включения/отключения звука
			"выключи|выруби|отключи": (power, "shutdown"), # команды для выключения
            "перезагрузи|ребутни": (power, "reboot"), # команды перезагрузки
			"усыпи|отправь спать": (power, "sleep"), # команды сна
			"отмени задачи|отменить задачи|отмени задачу|отменить задачу|отмени задача|отменить задача": cancel, # команды отмены задач управления питанием
            "чуть тише|потише|сделай чуть тише|сделай потише": (volumeDownX, 1),
            "чуть громче|погромче|сделай чуть громче|сделай погромче": (volumeUpX, 1),
            "тише|сделай тише": (volumeDownX, 3),
            "громче|сделай громче": (volumeUpX, 3),
            "запусти|включи": { # команды для запуска приложения
                "блокнот": (app_start, "notepad"), # название приложения
				"ютуб|ютьюб": (link_open, "youtube.com") # название ссылки
            }
        }
    }
    return manifest

time_templates = { # шаблоны фраз времени
	"quorter_hour": {
		"regex": "четверть(( \w+)+)? часа", # регулярное выражение для поиска во фразе
		"value": 15 # значение в минутах
	},
	"half_hour": {
		"regex": "полчаса",
		"value": 30
	},
	"one_and_half": {
		"regex": "(полтора(( \w+)+)? часа)|(часа(( \w+)+)? полтора)",
		"value": 90
	},
	"with_quorter": {
		"regex": "(\d+( .+)? )с четвертью час(а|ов)?",
		"value": 15
	},
	"with_half": {
		"regex": "(\d+( .+)? )с половиной час(а|ов)?",
		"value": 30
	},
	"hours": {
		"regex": "(\d+(( \w+)+)? час(а|ов)?)|(час(а|ов)?(( \w+)+)? \d+)|((один(( \w+)+)?)? час)",
		"value": 60
	},
	"minutes": {
		"regex": "(\d+(( \w+)+)? )?минут(у|ы)?((( \w+)+)? \d+)?",
		"value": 1
	},
}

states = {
    'device not exists': 'Устройство не найдено в списке',
    'device not response': 'Устройство не отвечает',
    'error': 'Ошибка',
    'uncaught error': 'Произошла ошибка',
    'task complete': 'Задача выполнена на клиенте'
}

def start_with_options(core:VACore, manifest:dict):
    pass

def num_matching(core:VACore, idx:int, ph_list:list):
	nums = {
        'units': { # разряды
            'ноль': 0,
            'нуль': 0,
            'один': 1,
            'одну': 1,
            'одна': 1,
            'два': 2,
            'две': 2,
            'три': 3,
            'четыре': 4,
            'пять': 5,
            'шесть': 6,
            'семь': 7,
            'восемь': 8,
            'девять': 9
        },
        'teens': {
            'десять': 10,
            'одиннадцать': 11,
            'двенадцать': 12,
            'тринадцать': 13,
            'четырнадцать': 14,
            'пятнадцать': 15,
            'шестнадцать': 16,
            'семнадцать': 17,
            'восемнадцать': 18,
            'девятнадцать': 19
        },
        'tens': {
            'двадцать': 20,
            'тридцать': 30,
            'сорок': 40,
            'пятьдесят': 50,
            'шестьдесят': 60,
            'семьдесят': 70,
            'восемьдесят': 80,
            'девяносто': 90
        },
        'hundreds': {
            'сто': 100,
            'двести': 200,
            'триста': 300,
            'четыреста': 400,
            'пятьсот': 500,
            'шестьсот': 600,
            'семьсот': 700,
            'восемьсот': 800,
            'девятьсот': 900
        },
        'thousands': {
            'тысяч(и|а|у)?': 1000,
            'миллион(а|ов)?': 1000000,
            'миллиард(а|ов)?': 1000000000
        }
    }

	for bit in nums:
		for numeric in nums[bit]:
			match = re.match('^'+numeric+'$', ph_list[idx])
			if match:
				return {'bit': bit, 'numeric': numeric, 'number': nums[bit][numeric]}
	return
    
def buildChain(core:VACore, idx:int, start_bit:str, ph_list:list):
    match = num_matching(core, idx, ph_list)
    chain = {'number': match['number'], 'end_chain': idx}
    if idx > 0:
        i = idx-1
        while i >= 0:
            sub_match = num_matching(core, i, ph_list)
            if sub_match:
                if match['bit'] == 'thousands' and sub_match['bit'] != 'thousands' and i == idx-1:
                    sub_chain = buildChain(core, i, match['bit'], ph_list)
                    number = match['number']*sub_chain['number']
                    chain['number'] = number
                    i = sub_chain['end_chain']
                    chain['end_chain'] = i
                    if i <= 0:
                        return chain
                elif match['bit'] == 'thousands' and sub_match['bit'] == 'thousands' and sub_match['number'] > match['number']:
                    sub_chain = buildChain(core, i, match['bit'], ph_list)
                    number = chain['number']+sub_chain['number']
                    chain['number'] = number
                    chain['end_chain'] = sub_chain['end_chain']
                    return chain
                elif sub_match['bit'] == 'units' or (sub_match['bit'] == 'thousands' and start_bit == 'thousands') or (match['bit'] == 'units' and sub_match['bit'] == 'teens') or (match['bit'] == 'teens' and sub_match['bit'] == 'tens') or sub_match['number'] < match['number'] or sub_match['bit'] == match['bit']:
                    return chain
                else:
                    sub_chain = buildChain(core, i, start_bit, ph_list)
                    number = chain['number']+sub_chain['number']
                    chain['number'] = number
                    chain['end_chain'] = sub_chain['end_chain']
                    return chain
            else:
                break
            i -= 1
    return chain

def numeric2number(core:VACore, phrase:str):
	ph_list = phrase.split()
	norm_phrase = ""

	i = len(ph_list)-1
	while i >= 0:
		match = num_matching(core, i, ph_list)
		if match:
			chain = buildChain(core, i, match['bit'], ph_list)
			word = str(chain['number'])
			i = chain['end_chain']
		else:
			word = ph_list[i]
		if i > 0:
			word = " " + word
		norm_phrase = word + norm_phrase
		i -= 1

	return norm_phrase

def get_client(core:VACore, phrase: str):
	options = core.plugin_options(modname)
	for client in options["reman_clients"]:
		pattern = "( |^)" + client + "( |$)"
		match = re.search(pattern, phrase)
		if match:
			return client

def search_digit(core:VACore, phrase:str):
	result = re.search(r'\d+', phrase)
	if result:
		digit = int(result.group(0))
		return digit
    
def get_delay(core:VACore, phrase:str):
	for template in time_templates:
		templ_d = time_templates[template]
		pattern = "( |^)" + templ_d["regex"] + "( |$)"
		match = re.search(pattern, phrase)
		if match:
			match_end = match.end()
			match_phrase = match.group(0)
			number = search_digit(core, match_phrase)
			if number is None:
				delay = templ_d["value"]
			elif template in ["hours", "minutes"]:
				delay = number*templ_d["value"]
			else:
				delay = number*60+templ_d["value"]
			
			if template == "hours": # если это часы, то ищем минуты в оставшейся части фразы
				end_phrase = phrase[match_end:]
				minutes = re.search(time_templates["minutes"]["regex"], end_phrase)
				if minutes:
					min_num = search_digit(core, minutes.group(0))
					if min_num:
						delay += min_num
					else:
						delay += time_templates["minutes"]["value"]
			return delay
	# непонятно, но сохраняем контекст и переспрашиваем время
	core.say("Через сколько нужно выполнить?")
	core.context_set(get_delay)

def power(core:VACore, phrase:str, cmd:str):
	client = get_client(core, phrase)
	if client:
		options = core.plugin_options(modname)
		
		client_prop = options["reman_clients"][client]
		names_list = client.split("|")
		client_name = names_list[0] # берём первое название для произношения помощником

		delay = 0
		match = re.search(r'через ', phrase)
		if match:
			phrase = numeric2number(core, phrase) # преобразуем числительные в числа
			match_delay = get_delay(core, phrase)
			if match_delay:
				delay = match_delay
				if delay > options["max_delay"]:
					core.play_voice_assistant_speech("Превышено максимальное время задержки")
					return

		url = "http://" + client_prop["ip"] + ":" + client_prop["port"] + "/power"
		parameters = dict(cmd=cmd, delay=delay)
		try:
			r = requests.get(url, params=parameters)
			if r:
				json_str = r.json()
				aDict = json.loads(json_str)
				if aDict['result'] == "ok" and delay > 0:
					core.play_voice_assistant_speech(aDict['detail'] + " на клиенте " + client_name)
				elif aDict['result'] == "ok" and delay == 0:
					core.play_voice_assistant_speech(states['task complete'] + " " + client_name)
				else:
					core.play_voice_assistant_speech(states['error'] + ". " + aDict['detail'])
			else:
				core.play_voice_assistant_speech(states['device not response'])
		except Exception as e:
			core.play_voice_assistant_speech(states['uncaught error'])
	else:
		core.play_voice_assistant_speech(states['device not exists'])
	return
    
def app_start(core:VACore, phrase:str, cmd:str):
	client = get_client(core, phrase)
	if client:
		options = core.plugin_options(modname)
		
		client_prop = options["reman_clients"][client]
		names_list = client.split("|")
		client_name = names_list[0] # берём первое название для произношения помощником
    
		url = "http://" + client_prop["ip"] + ":" + client_prop["port"] + "/application"
		parameters = dict(cmd=cmd)
		try:
			r = requests.get(url, params=parameters)
			if r:
				json_str = r.json()
				aDict = json.loads(json_str)
				if aDict['result'] == "ok":
					core.play_voice_assistant_speech(aDict['detail'] + " на клиенте " + client_name)
				else:
					core.play_voice_assistant_speech(states['error'] + ". " + aDict['detail'])
			else:
				core.play_voice_assistant_speech(states['device not response'])
		except Exception as e:
			core.play_voice_assistant_speech(states['uncaught error'])
	else:
		core.play_voice_assistant_speech(states['device not exists'])
	return

def link_open(core:VACore, phrase:str, cmd:str):
	client = get_client(core, phrase)
	if client:
		options = core.plugin_options(modname)
		
		client_prop = options["reman_clients"][client]
		names_list = client.split("|")
		client_name = names_list[0] # берём первое название для произношения помощником
    
		url = "http://" + client_prop["ip"] + ":" + client_prop["port"] + "/browser"
		parameters = dict(cmd=cmd)
		try:
			r = requests.get(url, params=parameters)
			if r:
				json_str = r.json()
				aDict = json.loads(json_str)
				if aDict['result'] == "ok":
					core.play_voice_assistant_speech(aDict['detail'] + " на клиенте " + client_name)
				else:
					core.play_voice_assistant_speech(states['error'] + ". " + aDict['detail'])
			else:
				core.play_voice_assistant_speech(states['device not response'])
		except Exception as e:
			core.play_voice_assistant_speech(states['uncaught error'])
	else:
		core.play_voice_assistant_speech(states['device not exists'])
	return

def cancel(core:VACore, phrase:str):
	client = get_client(core, phrase)
	if client:
		options = core.plugin_options(modname)

		client_prop = options["reman_clients"][client]
		names_list = client.split("|")
		client_name = names_list[0] # берём первое название для произношения помощником

		url = "http://" + client_prop["ip"] + ":" + client_prop["port"] + "/cancel"
		try:
			r = requests.get(url)
			if r:
				json_str = r.json()
				aDict = json.loads(json_str)
				if aDict['result'] == "ok":
					core.play_voice_assistant_speech(aDict['detail'] + " на клиенте " + client_name)
				else:
					core.play_voice_assistant_speech(states['error'] + ". " + aDict['detail'])
			else:
				core.play_voice_assistant_speech(states['device not response'])
		except Exception as e:
			core.play_voice_assistant_speech(states['uncaught error'])
	else:
		core.play_voice_assistant_speech(states['device not exists'])
	return

def volume_manager(core:VACore, phrase:str, point:int, cmd:str):
	client = get_client(core, phrase)
	if client:
		options = core.plugin_options(modname)

		client_prop = options["reman_clients"][client]
		names_list = client.split("|")
		client_name = names_list[0]
        
		url = "http://" + client_prop["ip"] + ":" + client_prop["port"] + "/volume"
		parameters = dict(cmd=cmd, point=point)
		try:
			r = requests.get(url, params=parameters)
			if r:
				json_str = r.json()
				aDict = json.loads(json_str)
				if aDict['result'] != "ok":
					core.play_voice_assistant_speech(states['error'] + ". " + aDict["detail"])
			else:
				core.play_voice_assistant_speech(states['device not response'])
		except Exception as e:
			core.play_voice_assistant_speech(states['uncaught error'])
	else:
		core.play_voice_assistant_speech(states['device not exists'])
	return

def volumeDownX(core:VACore, phrase:str, point:int):
	volume_manager(core, phrase, point, 'down')
	return
    
def volumeUpX(core:VACore, phrase:str, point:int):
	volume_manager(core, phrase, point, 'up')
	return
    
def toggle_mute(core:VACore, phrase:str):
	volume_manager(core, phrase, 0, 'mute')
	return

if __name__ == "__main__":
	cancel(None,"")