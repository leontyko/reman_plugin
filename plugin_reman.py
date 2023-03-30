# Remote manager plugin
# by Leonty Kopytov @leontyko

import requests
import re
import os
import json

from vacore import VACore
from utils.digitizer import Digitizer

modname = os.path.basename(__file__)[:-3] # calculating modname

# функция на старте
def start(core:VACore):
    manifest = { # возвращаем настройки плагина - словарь
        "name": "reMan", # имя
        "version": "1.1", # версия
        "require_online": False, # требует ли онлайн?
        
        "default_options": {
			"reman_clients" : {
				"ноутбук|ноут|ноутбуке|ноутбуки|ноутбука|ноуте|ноута": { # имена для определения клиента
					"ip": "127.0.0.1", # ip-адрес клиента
					"port": "8000" # порт клиента
				},
			},
            "max_delay": 1440 # максимальное время задержки - 24 часа
        },

        "commands": { # набор скиллов. Фразы скилла разделены | . Если найдены - вызывается функция
			"пауза|паузу|сделай паузу|поставь на паузу|останови|продолжай": play_pause,
			"дальше|вперед|переключи": next_track,
            "назад|переключи назад|предыдущий|предыдущую": prev_track,
            "без звука|выключи звук|выключить звук|выключай звук|со звуком|без мука|включи звук|верни звук": toggle_mute, # команды включения/отключения звука
			"выключи|выруби|отключи": (power, "shutdown"), # команды для выключения
            "перезагрузи|ребутни": (power, "reboot"), # команды перезагрузки
			"усыпи|отправь спать": (power, "sleep"), # команды сна
			"отмени задачи|отменить задачи|отмени задачу|отменить задачу|отмени задача|отменить задача": cancel, # команды отмены задач управления питанием
            "чуть тише|потише|сделай чуть тише|сделай потише": (volumeDownX, 1),
            "чуть громче|погромче|сделай чуть громче|сделай погромче": (volumeUpX, 1),
            "тише|сделай тише|звук тише": (volumeDownX, 3),
            "громче|сделай громче|звук громче": (volumeUpX, 3),
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
    'device_not_exists': 'Устройство не найдено в списке',
    'device_not_response': 'Устройство не отвечает',
    'error': 'Ошибка',
    'uncaught_error': 'Произошла ошибка',
    'task_complete': 'Задача выполнена на клиенте',
	'empty_clients': 'Клиенты не заданы',
	'whats_client': 'На каком клиенте выполнить?'
}

reman_context = {}

def start_with_options(core:VACore, manifest:dict):
    pass

def get_client(core:VACore, phrase:str):
	options = core.plugin_options(modname)
	for client in options["reman_clients"]:
		if len(options["reman_clients"].keys()) == 1: # Если задан всего один клиент
			return client
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

def power_manager(core:VACore, phrase:str):
	global reman_context
	options = core.plugin_options(modname)
	
	client_names = reman_context.get('client')
	if client_names is None:
		if len(options["reman_clients"].keys()) > 0:
			client_names = get_client(core, phrase)
			if client_names is None:
				if reman_context['counter'] < 5:
					reman_context['counter'] += 1
					core.say(states['whats_client'])
					core.context_set(power_manager)
					return
			else:
				reman_context['counter'] = 0
		else:
			core.play_voice_assistant_speech(states['empty_clients'])
			return

	if client_names:
		client_prop = options["reman_clients"][client_names]
		names_list = client_names.split("|")
		client_name = names_list[0] # берём первое название для произношения помощником

		delay = 0
		match = re.search(r'через ', reman_context['phrase'])
		
		if match:
			phrase = Digitizer.digitize(phrase) # на случай, если числа распознаются как числительные
			match_delay = get_delay(core, phrase)
			if match_delay:
				delay = match_delay
				if delay > options["max_delay"]:
					core.play_voice_assistant_speech("Превышено максимальное время задержки")
					reman_context = {}
					return
			elif reman_context['counter'] < 5:
				reman_context['counter'] += 1
				reman_context['client'] = client_names
				core.say("Через сколько нужно выполнить?")
				core.context_set(power_manager)
				return
			else:
				core.play_voice_assistant_speech('Не определено время задержки')
				reman_context = {}
				return

		cmd = reman_context['cmd']
		url = "http://" + client_prop["ip"] + ":" + client_prop["port"] + "/power"
		parameters = dict(cmd=cmd, delay=delay)
		try:
			r = requests.get(url, params=parameters)
			if r:
				json_str = r.json()
				data_dict = json.loads(json_str)
				if data_dict[0].get('result') == 'ok': and delay > 0:
					core.play_voice_assistant_speech(data_dict[0].get('detail') + " на клиенте " + client_name)
				elif data_dict[0].get('result') == 'ok' and delay == 0:
					core.play_voice_assistant_speech(states['task_complete'] + " " + client_name)
				else:
					core.play_voice_assistant_speech(states['error'] + ". " + data_dict[0].get('detail'))
			else:
				core.play_voice_assistant_speech(states['device_not_response'])
		except Exception as e:
			core.play_voice_assistant_speech(states['uncaught_error'])
	else:
		core.play_voice_assistant_speech(states['device_not_exists'])
	reman_context = {} # очищаем контекст
	return

def power(core:VACore, phrase:str, cmd:str):
	global reman_context
	reman_context['cmd'] = cmd
	reman_context['phrase'] = phrase
	reman_context['counter'] = 0
	power_manager(core, phrase)
	return
	
def app_start_manager(core:VACore, phrase:str):
	global reman_context
	options = core.plugin_options(modname)
	
	if len(options["reman_clients"].keys()) > 0:
		client_names = get_client(core, phrase)
		if client_names is None:
			if reman_context['counter'] < 5:
				reman_context['counter'] += 1
				core.say(states['whats_client'])
				core.context_set(app_start_manager)
				return
		else:
			cmd = reman_context['cmd']
		reman_context = {} # очищаем контекст
	else:
		core.play_voice_assistant_speech(states['empty_clients'])
		return

	if client_names:
		client_prop = options["reman_clients"][client_names]
		names_list = client_names.split("|")
		client_name = names_list[0] # берём первое название для произношения помощником
    
		url = "http://" + client_prop["ip"] + ":" + client_prop["port"] + "/application"
		parameters = dict(cmd=cmd)
		try:
			r = requests.get(url, params=parameters)
			if r:
				json_str = r.json()
				data_dict = json.loads(json_str)
				if data_dict[0].get('result') == 'ok':
					core.play_voice_assistant_speech(data_dict[0].get('detail') + " на клиенте " + client_name)
				else:
					core.play_voice_assistant_speech(states['error'] + ". " + data_dict[0].get('detail'))
			else:
				core.play_voice_assistant_speech(states['device_not_response'])
		except Exception as e:
			core.play_voice_assistant_speech(states['uncaught_error'])
	else:
		core.play_voice_assistant_speech(states['device_not_exists'])
	return

def app_start(core:VACore, phrase:str, cmd:str):
	global reman_context
	reman_context['cmd'] = cmd
	reman_context['counter'] = 0
	app_start_manager(core, phrase)
	return
	
def link_open_manager(core:VACore, phrase:str):
	global reman_context
	options = core.plugin_options(modname)
	
	if len(options["reman_clients"].keys()) > 0:
		client_names = get_client(core, phrase)
		if client_names is None:
			if reman_context['counter'] < 5:
				reman_context['counter'] += 1
				core.say(states['whats_client'])
				core.context_set(link_open_manager)
				return
		else:
			cmd = reman_context['cmd']
		reman_context = {} # очищаем контекст
	else:
		core.play_voice_assistant_speech(states['empty_clients'])
		return

	if client_names:
		client_prop = options["reman_clients"][client_names]
		names_list = client_names.split("|")
		client_name = names_list[0] # берём первое название для произношения помощником
    
		url = "http://" + client_prop["ip"] + ":" + client_prop["port"] + "/browser"
		parameters = dict(cmd=cmd)
		try:
			r = requests.get(url, params=parameters)
			if r:
				json_str = r.json()
				data_dict = json.loads(json_str)
				if data_dict[0].get('result') == 'ok':
					core.play_voice_assistant_speech(data_dict[0].get('detail') + " на клиенте " + client_name)
				else:
					core.play_voice_assistant_speech(states['error'] + ". " + data_dict[0].get('detail'))
			else:
				core.play_voice_assistant_speech(states['device_not_response'])
		except Exception as e:
			core.play_voice_assistant_speech(states['uncaught_error'])
	else:
		core.play_voice_assistant_speech(states['device_not_exists'])
	return

def link_open(core:VACore, phrase:str, cmd:str):
	global reman_context
	reman_context['cmd'] = cmd
	reman_context['counter'] = 0
	link_open_manager(core, phrase)
	return
	
def cancel(core:VACore, phrase:str):
	global reman_context
	options = core.plugin_options(modname)
	
	if len(options["reman_clients"].keys()) > 0:
		client_names = get_client(core, phrase)
		if client_names is None:
			if len(reman_context.keys()) == 0:
				reman_context['counter'] = 0
			if reman_context['counter'] < 5:
				reman_context['counter'] += 1
				core.say(states['whats_client'])
				core.context_set(cancel)
				return
		reman_context = {} # очищаем контекст
	else:
		core.play_voice_assistant_speech(states['empty_clients'])
		return

	if client_names:
		client_prop = options["reman_clients"][client_names]
		names_list = client_names.split("|")
		client_name = names_list[0] # берём первое название для произношения помощником

		url = "http://" + client_prop["ip"] + ":" + client_prop["port"] + "/cancel"
		try:
			r = requests.get(url)
			if r:
				json_str = r.json()
				data_dict = json.loads(json_str)
				if data_dict[0].get('result') == 'ok':
					core.play_voice_assistant_speech(data_dict[0].get('detail') + " на клиенте " + client_name)
				else:
					core.play_voice_assistant_speech(states['error'] + ". " + data_dict[0].get('detail'))
			else:
				core.play_voice_assistant_speech(states['device_not_response'])
		except Exception as e:
			core.play_voice_assistant_speech(states['uncaught_error'])
		return
	else:
		core.play_voice_assistant_speech(states['device_not_exists'])
	return

def volume_manager(core:VACore, phrase:str):
	global reman_context
	options = core.plugin_options(modname)

	if len(options["reman_clients"].keys()) > 0:
		client_names = get_client(core, phrase)
		if client_names is None:
			if reman_context['counter'] < 5:
				reman_context['counter'] += 1
				core.say(states['whats_client'])
				core.context_set(volume_manager)
				return
		else:
			cmd = reman_context['cmd']
			point = reman_context['point']
		reman_context = {} # очищаем контекст
	else:
		core.play_voice_assistant_speech(states['empty_clients'])
		return

	if client_names:
		client_prop = options["reman_clients"][client_names]
		names_list = client_names.split("|")
		client_name = names_list[0]
		
		url = "http://" + client_prop["ip"] + ":" + client_prop["port"] + "/volume"
		parameters = dict(cmd=cmd, point=point)
		try:
			r = requests.get(url, params=parameters)
			if r:
				json_str = r.json()
				data_dict = json.loads(json_str)
				if data_dict[0].get('result') != 'ok':
					core.play_voice_assistant_speech(states['error'] + ". " + data_dict[0].get('detail'))
			else:
				core.play_voice_assistant_speech(states['device_not_response'])
		except Exception as e:
			core.play_voice_assistant_speech(states['uncaught_error'])
	else:
		core.play_voice_assistant_speech(states['device_not_exists'])
		reman_context = {}
	return

def volumeDownX(core:VACore, phrase:str, point:int):
	global reman_context
	reman_context['cmd'] = 'down'
	reman_context['point'] = point
	reman_context['counter'] = 0
	volume_manager(core, phrase)
	return
    
def volumeUpX(core:VACore, phrase:str, point:int):
	global reman_context
	reman_context['cmd'] = 'up'
	reman_context['point'] = point
	reman_context['counter'] = 0
	volume_manager(core, phrase)
	return
    
def toggle_mute(core:VACore, phrase:str):
	global reman_context
	reman_context['cmd'] = 'mute'
	reman_context['point'] = 0
	reman_context['counter'] = 0
	volume_manager(core, phrase)
	return

def media_manager(core:VACore, cmd:str, client_names:str):
	options = core.plugin_options(modname)

	client_prop = options["reman_clients"][client_names]
	names_list = client_names.split("|")
	client_name = names_list[0]
	
	url = "http://" + client_prop["ip"] + ":" + client_prop["port"] + "/media"
	parameters = dict(cmd=cmd)
	try:
		r = requests.get(url, params=parameters)
		if r:
			json_str = r.json()
			data_dict = json.loads(json_str)
			if data_dict[0].get('result') != 'ok':
				core.play_voice_assistant_speech(states['error'] + ". " + data_dict[0].get('detail'))
		else:
			core.play_voice_assistant_speech(states['device_not_response'])
	except Exception as e:
		core.play_voice_assistant_speech(states['uncaught_error'])

def play_pause(core:VACore, phrase:str):
	global reman_context
	options = core.plugin_options(modname)

	if len(options["reman_clients"].keys()) > 0:
		client_names = get_client(core, phrase)
	else:
		core.play_voice_assistant_speech(states['empty_clients'])
		return

	if client_names:
		media_manager(core, 'playpause', client_names)
		reman_context = {}
	else:
		if len(reman_context.keys()) == 0:
			reman_context['counter'] = 0
		if reman_context['counter'] < 5:
			reman_context['counter'] += 1
			core.say(states['whats_client'])
			core.context_set(play_pause)
		else:
			core.play_voice_assistant_speech(states['device_not_exists'])
			reman_context = {}
	return

def next_track(core:VACore, phrase:str):
	global reman_context
	options = core.plugin_options(modname)

	if len(options["reman_clients"].keys()) > 0:
		client_names = get_client(core, phrase)
	else:
		core.play_voice_assistant_speech(states['empty_clients'])
		return

	if client_names:
		media_manager(core, 'nexttrack', client_names)
		reman_context = {}
	else:
		if len(reman_context.keys()) == 0:
			reman_context['counter'] = 0
		if reman_context['counter'] < 5:
			reman_context['counter'] += 1
			core.say(states['whats_client'])
			core.context_set(next_track)
		else:
			core.play_voice_assistant_speech(states['device_not_exists'])
			reman_context = {}
	return

def prev_track(core:VACore, phrase:str):
	global reman_context
	options = core.plugin_options(modname)

	if len(options["reman_clients"].keys()) > 0:
		client_names = get_client(core, phrase)
	else:
		core.play_voice_assistant_speech(states['empty_clients'])
		return

	if client_names:
		media_manager(core, 'prevtrack', client_names)
		reman_context = {}
	else:
		if len(reman_context.keys()) == 0:
			reman_context['counter'] = 0
		if reman_context['counter'] < 5:
			reman_context['counter'] += 1
			core.say(states['whats_client'])
			core.context_set(prev_track)
		else:
			core.play_voice_assistant_speech(states['device_not_exists'])
			reman_context = {}
	return

if __name__ == "__main__":
	cancel(None,"")