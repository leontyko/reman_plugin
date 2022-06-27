# reMan plugin

Плагин для [голосового ассистента Ирина](https://github.com/janvarev/Irene-Voice-Assistant), работающий с [клиентом reMan](https://github.com/leontyko/reman_client)

## Конфигурация

1. В секции ```default_options``` пропишите параметры клиентов в подсекции ```reman_clients``` как указано в примере.

2. В параметре ```max_delay``` можно указать ограничение максимального времени задержки команд управления питанием в минутах (по умолчанию - сутки).

3. В секции ```commands``` указываются команды отправляемые клиенту. Подробнее с командыми можно ознакомиться на странице [клиента reMan](https://github.com/leontyko/reman_client).

## Запуск

Для начала работы загрузите [голосовой помощник](https://github.com/janvarev/Irene-Voice-Assistant) и поместите плагин в папку ```plugins```.

Плагин может конфликтовать с другими медиа-плагинами из-за одинаковых команд. Рекомендуется отключить схожие команды в одном из плагинов или использовать только один из медиа-плагинов.