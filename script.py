import asyncio
import ipaddress
import json
import os
from pathlib import Path

import aiodns
import aiohttp
from tqdm.asyncio import tqdm


def list_from_file(path):
    with open(path, encoding='utf8') as f_:
        return [x for x in f_.read().split('\n') if len(x)]


ROOT_PATH = Path(os.path.dirname(os.path.abspath(__file__)))
GOOGLE_IPS_PATH = ROOT_PATH / 'google-ipv4.txt'
DOMAINS_PATH = ROOT_PATH / 'data/domains.txt'
GOOGLE_OPEN_PATH = ROOT_PATH / 'data/google-open.txt'
GOOGLE_BLOCK_PATH = ROOT_PATH / 'data/google-block.txt'
EXCLUDED_DOMAINS_PATH = ROOT_PATH / 'data/skip.txt'
RETRIES = 3
DNS_RESOLVER = aiodns.DNSResolver(nameservers=['8.8.8.8', '8.8.4.4'])
GOOGLE_IPS = set(list_from_file(GOOGLE_IPS_PATH))

if EXCLUDED_DOMAINS_PATH.is_file():
    EXCLUDED_DOMAINS = set(list_from_file(EXCLUDED_DOMAINS_PATH))
else:
    EXCLUDED_DOMAINS = set()


async def async_script():

    def _drop_nan(data):
        _is_nan = lambda x: isinstance(x, type(None))
        data_ = {x for x in data if not _is_nan(x)}
        if isinstance(data, list):
            data_ = list(data_)
        return data_

    async def resolve(domain):
        for _ in range(RETRIES):
            try:
                res = await DNS_RESOLVER.query(domain, 'A')
                assert len(res)
                return (domain, res[0].host)
            except (aiodns.error.DNSError, AssertionError):
                continue
        return None

    def is_google(ip_addr):
        for google_ip in GOOGLE_IPS:
            if ipaddress.ip_address(ip_addr) in ipaddress.ip_network(
                    google_ip):
                return True
        return False

    async def is_open(domain):
        async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=60),
                raise_for_status=False) as session:
            for _ in range(RETRIES):
                try:
                    async with session.get('https://' + domain) as resp:
                        if resp.status != 403:
                            return domain
                        return None
                except (aiohttp.ClientError, asyncio.TimeoutError):
                    continue
        return None

    #  ..........
    domains = {
        x
        for x in list_from_file(DOMAINS_PATH)
        if not any(map(x.endswith, EXCLUDED_DOMAINS))
    }
    print('unique domains provided:', len(domains))
    #  ..........
    tasks = {resolve(dom) for dom in domains}
    print('resolving domains...')
    domains = _drop_nan(set(await tqdm.gather(*tasks)))
    print('domains resolved:', len(domains))
    #  ..........
    domains = {x[0] for x in domains if is_google(x[1])}
    print('google backed domains:', len(domains))
    #  ..........
    tasks = {is_open(dom) for dom in domains}
    print('testing google domains...')
    open_domains = _drop_nan(set(await tqdm.gather(*tasks)))
    blocked_domains = domains - open_domains
    print('open domains:', len(open_domains))
    print('blocked domains:', len(blocked_domains))
    #  ..........
    with open(GOOGLE_OPEN_PATH, 'w') as f_:
        f_.write('\n'.join(open_domains))
    with open(GOOGLE_BLOCK_PATH, 'w') as f_:
        f_.write('\n'.join(blocked_domains))


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(async_script())
