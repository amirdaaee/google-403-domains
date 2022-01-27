import asyncio
import ipaddress
import json
import os
from pathlib import Path

import aiodns
import aiohttp
from tqdm.asyncio import tqdm

ROOT_PATH = Path(os.path.dirname(os.path.abspath(__file__)))
GOOGLE_IPS_PATH = ROOT_PATH / 'google-ipv4.txt'
DOMAINS_PATH = ROOT_PATH / 'data/domains.txt'
GOOGLE_OPEN_PATH = ROOT_PATH / 'data/google-open.json'
GOOGLE_BLOCK_PATH = ROOT_PATH / 'data/google-block.json'

DNS_RESOLVER = aiodns.DNSResolver(nameservers=['8.8.8.8', '8.8.4.4'])
with open(GOOGLE_IPS_PATH, encoding='utf8') as google_ipv4_file:
    GOOGLE_IPS = [x for x in google_ipv4_file.read().split('\n') if len(x)]


async def async_script():

    def _drop_nan(data):
        _is_nan = lambda x: isinstance(x, type(None))
        data_ = {x for x in data if not _is_nan(x)}
        if isinstance(data, list):
            data_ = list(data_)
        return data_

    def load_data():
        with open(DOMAINS_PATH) as f_:
            return f_.read().split('\n')

    async def resolve(domain):
        try:
            res = await DNS_RESOLVER.query(domain, 'A')
            assert len(res)
            return (domain, res[0].host)
        except (aiodns.error.DNSError, AssertionError):
            return None

    def is_google(ip_addr):
        for google_ip in GOOGLE_IPS:
            if ipaddress.ip_address(ip_addr) in ipaddress.ip_network(
                    google_ip):
                return True
        return False

    async def is_blocked(domain):
        async with aiohttp.ClientSession() as session:
            async with session.get('https://' + domain) as resp:
                if resp.status == 403:
                    return domain
        return None

    #  ..........
    domains = load_data()
    print('provided domains:', len(domains))
    #  ..........
    domains = set(domains)
    print('unique domains:', len(domains))
    #  ..........
    tasks = {resolve(dom) for dom in domains}
    print('resolving domains...')
    domains = _drop_nan(await tqdm.gather(*tasks))
    print('domains resolved:', len(domains))
    #  ..........
    domains = {x[0] for x in domains if is_google(x[1])}
    print('google backed domains:', len(domains))
    #  ..........
    tasks = {is_blocked(dom) for dom in domains}
    print('testing google domains...')
    blocked_domains = _drop_nan(await tqdm.gather(*tasks))
    open_domains = domains.difference(blocked_domains)
    print('blocked domains:', len(blocked_domains))
    #  ..........
    with open(GOOGLE_OPEN_PATH, 'w') as f_:
        json.dump(list(open_domains), f_)
    with open(GOOGLE_BLOCK_PATH, 'w') as f_:
        json.dump(list(blocked_domains), f_)


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(async_script())
