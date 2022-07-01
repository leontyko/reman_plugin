# Digitizer
# Allows to convert numerals to numbers
# by Leonty Kopytov @leontyko

import re

class Digitizer:
	def _num_matching(self, idx:int, ph_list:list):
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
	
	def _buildChain(self, idx:int, start_bit:str, ph_list:list):
		match = self._num_matching(self, idx, ph_list)
		chain = {'number': match['number'], 'end_chain': idx}
		if idx > 0:
			i = idx-1
			while i >= 0:
				sub_match = self._num_matching(self, i, ph_list)
				if sub_match:
					if match['bit'] == 'thousands' and sub_match['bit'] != 'thousands' and i == idx-1:
						sub_chain = self._buildChain(self, i, match['bit'], ph_list)
						number = match['number']*sub_chain['number']
						chain['number'] = number
						i = sub_chain['end_chain']
						chain['end_chain'] = i
						if i <= 0:
							return chain
					elif match['bit'] == 'thousands' and sub_match['bit'] == 'thousands' and sub_match['number'] > match['number']:
						sub_chain = self._buildChain(self, i, match['bit'], ph_list)
						number = chain['number']+sub_chain['number']
						chain['number'] = number
						chain['end_chain'] = sub_chain['end_chain']
						return chain
					elif sub_match['bit'] == 'units' or (sub_match['bit'] == 'thousands' and start_bit == 'thousands') or (match['bit'] == 'units' and sub_match['bit'] == 'teens') or (match['bit'] == 'teens' and sub_match['bit'] == 'tens') or sub_match['number'] < match['number'] or sub_match['bit'] == match['bit']:
						return chain
					else:
						sub_chain = self._buildChain(self, i, start_bit, ph_list)
						number = chain['number']+sub_chain['number']
						chain['number'] = number
						chain['end_chain'] = sub_chain['end_chain']
						return chain
				else:
					break
				i -= 1
		return chain
	
	@classmethod
	def digitize(cls, phrase:str):
		ph_list = phrase.split()
		norm_phrase = ""

		i = len(ph_list)-1
		while i >= 0:
			match = cls._num_matching(cls, i, ph_list)
			if match:
				chain = cls._buildChain(cls, i, match['bit'], ph_list)
				word = str(chain['number'])
				i = chain['end_chain']
			else:
				word = ph_list[i]
			if i > 0:
				word = " " + word
			norm_phrase = word + norm_phrase
			i -= 1

		return norm_phrase