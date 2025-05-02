import concurrent
import json
import math
import random
import re
import time
import traceback
from datetime import datetime
from decimal import Decimal
from typing import Optional, Any, Dict
from enum import Enum
import concurrent.futures
import threading
from mnemonic import Mnemonic
from bip32utils import BIP32Key, BIP32_HARDEN
from eth_keys import keys
import requests
from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware
from eth_account import Account
from utils import logger
import pandas as pd

from excel_functions import get_profile_for_work, write_cell

# Количество потоков
MAX_THREADS = 8
# Пауза между отправкой аккаунтов в работу
SLEEP_BETWEEN_ACC = [2, 8]





ACCOUNT_FILE = "gm_ink.xlsx"

RPC = [
    "https://rpc-gel.inkonchain.com",
	"https://rpc-qnd.inkonchain.com",
	"https://ink.drpc.org",
	"https://57073.rpc.thirdweb.com/"
]

GM_CONTRACT = "0x9F500d075118272B3564ac6Ef2c70a9067Fd2d3F"

GM_ABI = """[{"anonymous":false,"inputs":[{"indexed":true,"internalType":"address","name":"user","type":"address"},{"indexed":true,"internalType":"address","name":"recipient","type":"address"}],"name":"GM","type":"event"},{"inputs":[],"name":"gm","outputs":[],"stateMutability":"nonpayable","type":"function"},{"inputs":[{"internalType":"address","name":"recipient","type":"address"}],"name":"gmTo","outputs":[],"stateMutability":"nonpayable","type":"function"},{"inputs":[{"internalType":"address","name":"user","type":"address"}],"name":"lastGM","outputs":[{"internalType":"uint256","name":"lastGM","type":"uint256"}],"stateMutability":"view","type":"function"}]"""

def data_is_none(value):
    if value is None or value == '' or (isinstance(value, float) and math.isnan(value)) or pd.isna(value):
        return True
    else:
        return False

def check_wallet_data(wallet_data: str):
    words = wallet_data.split()

    if len(words) in [12, 15, 18, 21, 24]:
        mnemo = Mnemonic("english")
        if all(word in mnemo.wordlist for word in words):
            return "seed"

    if re.fullmatch(r"^(0x)?[0-9a-fA-F]{64}$", wallet_data):
        try:
            acc = Account.from_key(wallet_data)
            return "private_key"
        except:
            pass

    return "private_key"

def get_wallet_data(wallet_data: str):
    type_wallet_data = check_wallet_data(wallet_data)

    if type_wallet_data == "seed":
        mnemo = Mnemonic("english")
        seed = mnemo.to_seed(wallet_data)

        root_key = BIP32Key.fromEntropy(seed)
        child_key = root_key.ChildKey(44 + BIP32_HARDEN).ChildKey(60 + BIP32_HARDEN).ChildKey(
            0 + BIP32_HARDEN).ChildKey(0).ChildKey(0)

        private_key_bytes = child_key.PrivateKey()
        private_key_hex = private_key_bytes.hex()

        public_key_bytes = keys.PrivateKey(bytes.fromhex(private_key_hex)).public_key
        wallet_address = Web3.to_checksum_address (public_key_bytes.to_checksum_address())
        return [private_key_hex, wallet_address]

    if type_wallet_data == "private_key":
        account = Account.from_key(wallet_data)
        wallet_address = Web3.to_checksum_address(account.address)
        return [wallet_data, wallet_address]
    return None

def masked_wallet(address):
	try:
		if len(address) >= 10:
			return f"{address[:6]}...{address[-4:]}"
	except:
		return None

def proxy_formated(proxy: str):
    # Определение протокола
    try:
        protocol = re.findall(r".*?(?=://)", proxy)[0].lower()
    except IndexError:
        protocol = "http"

    # Получение строки прокси без протокола
    try:
        proxy_str = re.findall(r"(?<=://).*", proxy)[0]
    except IndexError:
        proxy_str = proxy

    # Определение формата прокси
    try:
        log_pass, ip_port = proxy_str.split('@')
        proxy_format = "LOGIN_PASSWORD_IP_PORT"
    except ValueError:
        ip_port = proxy_str
        proxy_format = "IP_PORT"

    # Обработка прокси в формате IP:PORT
    if proxy_format == "IP_PORT":
        proxy_ip, proxy_port = ip_port.split(':')
        return protocol, proxy_ip, proxy_port

    # Обработка прокси в формате LOGIN:PASS@IP:PORT
    if proxy_format == "LOGIN_PASSWORD_IP_PORT":
        log_pass, ip_port = proxy_str.split('@')
        proxy_login, proxy_password = log_pass.split(':')
        proxy_ip, proxy_port = ip_port.split(':')

        return protocol, proxy_ip, proxy_port, proxy_login, proxy_password

def get_rpc():
	ink = [
		"https://rpc-gel.inkonchain.com",
		"https://rpc-qnd.inkonchain.com",
		"https://ink.drpc.org",
		"https://57073.rpc.thirdweb.com/"
	]
	return random.choice(ink)

def web3_connect(proxy=None):
	attempts = 0
	while attempts < 10:
		try:
			attempts += 1
			RPC_URL = get_rpc()

			if proxy is not None:
				session = requests.Session()
				session.proxies.update({
					"http": proxy,
					"https": proxy
				})

				provider = Web3.HTTPProvider(RPC_URL)
				provider.session = session
				web3 = Web3(provider)

			else:
				web3 = Web3(Web3.HTTPProvider(RPC_URL))

			web3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)

			if not web3.is_connected():
				time.sleep(random.randint(1, 3))
				web3.provider = None
			else:
				return web3
		except:
			pass

	return None

def check_transaction(tx_hash, proxy=None, web3object: Optional[Web3] = None):
	success = False
	time_sleep = 10
	attempts = 0
	max_attempts = 20

	while not success and attempts < max_attempts:
		attempts += 1
		try:
			if web3object is None:
				web3 = web3_connect(proxy)
			else:
				web3 = web3object

			tx_receipt = web3.eth.get_transaction_receipt(tx_hash)
			if tx_receipt['status'] == 1:
				return True
			elif tx_receipt['status'] == 0 and attempts > 1:
				return False
			else:
				pass
		except Exception as e:
			if attempts == max_attempts - 2:
				logger.error(f"Ошибка при проверке транзакции {tx_hash}: {e}")
				return None

			if attempts % 6 == 0:
				logger.warning(f"Проверяем транзакцию: {tx_hash} - {attempts} попытка. Ошибка: {e}")

		time.sleep(time_sleep)

class GM_Daily:
	def __init__(self, evm_private_key: str, web3: Optional[Web3] = None, proxy: Optional[str] = None, acc_number: Optional[Any] = None):
		self.account = Account.from_key(evm_private_key)
		self.proxy = {"http": proxy, "https": proxy} if proxy else None
		self.total_attempts = 5
		self.wallet_masked = masked_wallet(self.account.address)
		self.account_number = acc_number
		if web3 is None:
			self.web3 = web3_connect(self.proxy)
		else:
			self.web3 = web3

	def get_gas_params(self) -> Dict[str, int]:
		latest_block = self.web3.eth.get_block("latest")
		base_fee = latest_block["baseFeePerGas"]
		max_priority_fee = self.web3.eth.max_priority_fee

		max_fee = base_fee + max_priority_fee

		return {
			"maxFeePerGas": max_fee,
			"maxPriorityFeePerGas": max_priority_fee,
		}

	def get_last_gm(self):
		attempts = 0

		while attempts < self.total_attempts:
			attempts += 1
			try:

				contract = self.web3.eth.contract(
					address=self.web3.to_checksum_address(GM_CONTRACT),
					abi=json.loads(GM_ABI)
				)
				calls = contract.functions.lastGM (str(self.account.address)).call()
				return calls

			except Exception as e:
				if attempts == self.total_attempts - 1:
					logger.error(
						f"[ {self.wallet_masked} ] | {self.account_number} | GM_Ink (lastGm) error: {e}")
				pass

			time.sleep(random.randint(1, 2))

		return None

	def gm(self):
		attempts = 0

		while attempts < self.total_attempts:
			attempts += 1
			try:

				contract = self.web3.eth.contract(
					address=self.web3.to_checksum_address(GM_CONTRACT),
					abi=json.loads(GM_ABI)
				)
				calls = contract.functions.gm()

				gas_params = self.get_gas_params()

				transaction = {
					"from": self.account.address,
					"to": self.web3.to_checksum_address(GM_CONTRACT),
					"data": calls._encode_transaction_data(),
					"value": 0,
					"chainId": 57073,
					"type": 2,
				}

				estimated_gas = self.web3.eth.estimate_gas(transaction) * random.uniform(1.1, 1.3)

				transaction.update(
					{
						"nonce": self.web3.eth.get_transaction_count(self.account.address, "latest", ),
						"gas": int(estimated_gas),
						**gas_params,
					}
				)
				signed_tx = self.web3.eth.account.sign_transaction(transaction, self.account.key)
				tx_hash = self.web3.eth.send_raw_transaction(signed_tx.raw_transaction)

				logger.warning(f"[ {self.wallet_masked} ] | {self.account_number} | "
							   f"GM_Ink (send GM) : отправили GM")

				tx_id = Web3.to_hex(tx_hash)
				return tx_id

			except Exception as e:
				if attempts == self.total_attempts - 1:
					logger.error(
						f"[ {self.wallet_masked} ] | {self.account_number} | GM_Ink (send GM) error: {e}")
				pass

			time.sleep(random.randint(1, 2))

		return None

	def check_tx(self):
		gm_tx = self.gm()
		complete_tx = check_transaction(gm_tx, self.proxy, self.web3)
		if complete_tx:
			logger.warning(f"[ {self.wallet_masked} ] | {self.account_number} | "
						   f"GM_Ink (send GM) : успешная отправка GM - {gm_tx}")
			time.sleep(random.randint(1, 2))
			return "Success"
		else:
			logger.error(f"[ {self.wallet_masked} ] | {self.account_number} | "
						 f"GM_Ink (send GM) : транзакция Failed или произошла другая ошибка - {gm_tx}")
			return "Error"

	def send_gm(self):
		tx = None
		_last_gm = self.get_last_gm()
		if int(time.time()) >= _last_gm + (60 * 60 * 24):
			tx = self.check_tx()
		else:
			logger.error(f"[ {self.wallet_masked} ] | {self.account_number} | "
						 f"GM_Ink (send GM) : время отправки GM еще не наступило!")
			tx = "Время отправки GM еще не наступило!"

		return tx

def process_wallet(account_data):
	number_profile = account_data["NUMBER_WALLET"]
	evm_seed_phrase = account_data["EVM_SEED_PHRASE"]
	evm_wallet_address = account_data["EVM_WALLET_ADDRESS"]
	evm_private_key = account_data["EVM_PRIVATE_KEY"]
	proxy = account_data["PROXY"]

	write_cell(ACCOUNT_FILE, "STATUS", number_profile, "TRUE")  # Записать TRUE в таблицу аккаунтов

	try:
		if proxy.lower() == "no_proxy":
			proxy = None
		else:
			proxy_data = proxy_formated(proxy)
			if len(proxy_data) == 3:
				proxy = f"{proxy_data[0]}://{proxy_data[1]}:{proxy_data[2]}"

			if len(proxy_data) == 5:
				proxy = f"{proxy_data[0]}://{proxy_data[3]}:{proxy_data[4]}@{proxy_data[1]}:{proxy_data[2]}"
	except:
		raise Exception("Не верный формат прокси: {proxy}")

	if (data_is_none(evm_wallet_address) or data_is_none(evm_private_key)) and not data_is_none(evm_seed_phrase):
		wallet_data = get_wallet_data(evm_seed_phrase)
		evm_private_key = wallet_data[0]
		write_cell(ACCOUNT_FILE, "EVM_PRIVATE_KEY", number_profile, evm_private_key)
		evm_wallet_address = Account.from_key(evm_private_key).address
		write_cell(ACCOUNT_FILE, "EVM_WALLET_ADDRESS", number_profile, evm_wallet_address)

	if (data_is_none(evm_seed_phrase) and data_is_none(evm_wallet_address)) and not data_is_none(evm_private_key):
		wallet_data = get_wallet_data(evm_private_key)
		evm_wallet_address = Account.from_key(evm_private_key).address
		write_cell(ACCOUNT_FILE, "EVM_WALLET_ADDRESS", number_profile, evm_wallet_address)

	wallet_masked = masked_wallet(evm_wallet_address)

	if data_is_none(evm_wallet_address) or data_is_none(evm_private_key):
		logger.error(f"[ {wallet_masked} ] | {number_profile} | Не удалось получить данные кошелька!")
		write_cell(ACCOUNT_FILE, "ERROR_ID", number_profile, "Не удалось получить данные кошелька!")
		raise Exception
	else:
		logger.warning(f"[ {wallet_masked} ] | {number_profile} | Кошелек отправлен в работу......")
		tx = GM_Daily(evm_private_key, None, proxy, number_profile).send_gm()
		try:
			write_cell(ACCOUNT_FILE, "GM_INK", number_profile, tx)
		except:
			pass







def main():
	print("======== WEB3 | GM INKONCHAIN ========")
    	print(f"Наши ресурсы:\n"
          f"Telegram-канал: @quantumlab_official\n"
          f"Продукты: @quantum_lab_bot\n\n")
	account_file_name = ACCOUNT_FILE
	accounts_for_work = get_profile_for_work(account_file_name)

	if len(accounts_for_work) > 0:
		logger.warning(f"Запуск активности в {MAX_THREADS} потоков")
		logger.warning(f"В работу отправлено: {len(accounts_for_work)} аккаунтов")

		random.shuffle(accounts_for_work)

		with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
			futures = []
			for account_data in accounts_for_work:
				logger.error(f"Автоматизация и разработка by QUANTUM LAB | Telegram-канал: @quantumlab_official | Продукты: @quantum_lab_bot")
				futures.append(executor.submit(process_wallet, account_data))
				time.sleep(random.randint(*SLEEP_BETWEEN_ACC))

			for future in concurrent.futures.as_completed(futures):
				try:
					future.result()
				except Exception as e:
					logger.error(f"Ошибка: {e}")
					logger.error(traceback.format_exc())

	else:
		logger.warning(f"❌ Нет аккаунтов для работы! Проверьте данные в таблице!")

	
    	print(f"Наши ресурсы:\n"
          f"Telegram-канал: @quantumlab_official\n"
          f"Продукты: @quantum_lab_bot\n\n")
	print("======== WEB3 | GM INKONCHAIN ========")

main()
