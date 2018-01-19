import os
from selenium import webdriver
import requests
from bs4 import BeautifulSoup
import re
from itertools import islice
from collections import OrderedDict
import pandas as pd
import time
import functools


Communities_Info_Col = [u'小区名称', u'大区域', u'小区域', u'建造时间', u'挂牌均价', u'在售套数', u'链接']
Properties_Info_Col = ['小区名字', '大区域', '小区域', '建造时间', '单价','房型', '面积', '楼层', '朝向',
                       '价格', '描述', '地铁', '满五', '有钥匙', '新上', '链接']
Transitions_Info_Col = ['小区名字', '大区域', '小区域', '价格','交易时间','面积','房型', '单价', '楼层',
                        '朝向', '装修', '链接']
Home_url = u"http://sh.lianjia.com"
Lianjia_Account = ''
Lianjia_Password = ''
Cookies = None
Req = None


def stop_time(f):
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        start = time.time()
        res = f(*args, **kwargs)
        print('%s execute %s s ' % (f, time.time()-start))
        return res
    return wrapper


@stop_time
def login():
    chrome_path= r"C:\Program Files (x86)\chromedriver_win32\chromedriver.exe"
    wd = webdriver.Chrome(executable_path=chrome_path)
    login_url = 'http://passport.lianjia.com/cas/login?service=http%3A%2F%2Fuser.sh.lianjia.com%2Findex'
    wd.get(login_url)

    wd.find_element_by_xpath('//*[@id="username"]').send_keys(Lianjia_Account)
    wd.find_element_by_xpath('//*[@id="password"]').send_keys(Lianjia_Password)
    wd.find_element_by_xpath('//*[@id="loginUserForm"]/ul/li[5]/button').click()

    req = requests.Session() #构建Session
    global Cookies
    Cookies = wd.get_cookies() #导出cookie


def get_req():
    global Req
    global Cookies
    if Req:
        return Req
    Req = requests.Session()  # 构建Session
    for cookie in Cookies:
        Req.cookies.set(cookie['name'], cookie['value'])  # 转换cookies
    return Req


def do_request(url):
    req = get_req()
    for i in range(5):
        try:
            res = req.get(url)
        except (ConnectionResetError, requests.exceptions.ConnectionError):
            print('open %s failed and try %sth in 5s' % (url, i+2))
            time.sleep(5)
        else:
            break
    return res


@stop_time
def district_spider():
    url = u"/xiaoqu/"
    plain_text = do_request(Home_url + url).text
    soup = BeautifulSoup(plain_text, 'lxml')
    area_tags = soup.find('div', {'class': 'option-list gio_district'}).findAll('a')
    big_areas = OrderedDict()
    for i in islice(area_tags, 1, len(area_tags) - 1):
        href = i.get('href')
        href = href[href.rfind('/', 0, len(href) - 1) + 1:-1]
        big_areas[href] = list()
        big_areas[href].append(i.text)

        plain_text = do_request(Home_url + url + href).text
        sub_area_soup = BeautifulSoup(plain_text, 'lxml')
        sub_area_tags = sub_area_soup.find('div', {'class': 'option-list sub-option-list gio_plate'}).findAll('a')
        for j in islice(sub_area_tags, 1, len(sub_area_tags)):
            sub_href = j.get('href')
            sub_href = sub_href[sub_href.rfind('/', 0, len(sub_href)-1)+1:-1]
            big_areas[href].append((sub_href, j.text))
    return big_areas


def xiaoqu_spider(url_page):
    """
    爬取页面链接中的小区信息
    """
    #try:
    #print('search %s' % url_page)
    plain_text = do_request(url_page).text
    soup = BeautifulSoup(plain_text, 'lxml')
    # except (urllib2.HTTPError, urllib2.URLError) as e:

    xiaoqu_list = soup.findAll('div', {'class': 'info-panel'})
    community_list = list()
    for xq in xiaoqu_list:
        community_info = list()
        community_info.append(xq.find('a').text)
        area_tag = xq.find('div', {'class': 'con'})
        area = area_tag.findAll('a')

        community_info.append(area[0].text)
        community_info.append(area[1].text)
        area_content = area_tag.text
        pattern = re.compile(r'\s+')
        area_content = re.sub(pattern, '', area_content)
        info = re.match(r'.*｜(.*)年建成', area_content)
        if info:
            community_info.append(int(info.groups()[0][-4:]))
        else:
            community_info.append(info)

        price = xq.find('div', {'class': 'price'}).span.text.strip()
        price = int(price) if price.isdigit() else None
        stock_num = int(xq.find('div', {'class': 'square'}).a.span.text.strip())
        href = xq.find('div', {'class': 'square'}).a.get('href')

        community_info.append(price)
        community_info.append(stock_num)
        community_info.append(href)
        community_list.append(community_info)
    return community_list


@stop_time
def do_xiaoqu_spider(big_areas):
    """
    爬取大区域中的所有小区信息
    """
    xiaoqu_url = u'/xiaoqu/'
    #查找大区域
    results = list()
    for area in big_areas.values():
        for sub_area in islice(area, 1, len(area)):
            url = Home_url+xiaoqu_url+sub_area[0]

            plain_text = do_request(url).text
            soup = BeautifulSoup(plain_text, 'lxml')
            page_div = soup.find('div', {'class': 'page-box house-lst-page-box'})
            total_pages = page_div.find('a', {'gahref': 'results_totalpage'})
            if total_pages:
                total_pages = int(total_pages.text)
            else:
                page_a_num = len(page_div.findAll('a'))
                total_pages = page_a_num - 1 if page_a_num > 2 else page_a_num

            for i in range(total_pages):
                url_page = url + u"/d%s" % (i + 1)
                results.extend(xiaoqu_spider(url_page))
            print('current communities %s %s %s' % (len(results), area[0], sub_area[1]))
    #process_pool.join()
    return results

def property_spider(url_page):
    """
    爬取页面链接中的小区信息
    """
    #try:
    #print('search %s' % url_page)
    plain_text = do_request(url_page).text
    soup = BeautifulSoup(plain_text, 'lxml')
    # except (urllib2.HTTPError, urllib2.URLError) as e:

    xiaoqu_list = soup.findAll('div', {'class': 'info'})
    property_list = list()
    for prop in xiaoqu_list:

        property_info = list()
        try:
            row2 = prop.find('span', {'class':'info-col row2-text'})
            name = row2.findAll('a')
            property_info.append(name[0].text)#小区名字
            property_info.append(name[1].text)  # 大区域
            property_info.append(name[2].text)  # 小区域
            year = re.findall('(\d+)年', row2.text)
            property_info.append(year[0] if year else None) #建造时间
            price_item = prop.find('span', {'class': 'info-col price-item minor'})
            price_item = re.findall('(\d+)', price_item.text) if price_item else None
            property_info.append(price_item[0] if price_item else None)  # 单价
            row1 = prop.find('span', {'class': 'info-col row1-text'})
            row1_info = re.match('\s+(.+)\|(.+)平\s+\|(.+)\s+\|?(.*)\s+', row1.text)
            if not row1_info:
                print(row1.text)
                raise
            row1_info = row1_info.groups()
            property_info.append(row1_info[0])#房型
            property_info.append(row1_info[1]) # 面积
            property_info.append(row1_info[2])  # 楼层
            property_info.append(row1_info[3])  # 朝向

            total_price = prop.find('span', {'class': 'total-price strong-num'}).text
            property_info.append(total_price)  # 价格

            des = prop.find('a', {'class': 'text link-hover-green js_triggerGray js_fanglist_title'})
            property_info.append(des.text)  # 描述

            tag2s = prop.find('div', {'class': 'property-tag-container'}).findAll('span')
            str_other = ''
            for tag in tag2s:
                str_other += tag.text
            re_res = re.search(r'距离.*米', str_other)
            property_info.append(re_res.group() if re_res else None)#地铁

            re_res = re.search(r'满(五|二)', str_other)
            property_info.append(re_res.group() if re_res else None)#满五

            re_res = re.search(r'有钥匙', str_other)
            property_info.append(re_res.group() if re_res else None)#有钥匙

            new = prop.find('span', {'class': 'c-prop-tag c-prop-tag--blue'})
            a = 1
            property_info.append(1 if new else None)#新上
            property_info.append(des.get('href'))#链接
        except IndexError:
            raise IndexError
        property_list.append(property_info)
    return property_list


@stop_time
def do_property_spider(big_areas, start=0):
    """
    爬取大区域中的所有小区信息
    """
    xiaoqu_url = u'/ershoufang/'
    #查找大区域
    results = list()
    for area in islice(big_areas.values(), start, len(big_areas)):
        for sub_area in islice(area, 1, len(area)):
            url = Home_url+xiaoqu_url+sub_area[0]

            plain_text = do_request(url).text
            soup = BeautifulSoup(plain_text, 'lxml')
            page_div = soup.find('div', {'class': 'c-pagination'})
            if not page_div:
                print('not find page %s %s' % (area[0], sub_area[0]))
                continue
            total_pages = page_div.find('a', {'gahref': 'results_totalpage'})
            if total_pages:
                total_pages = int(total_pages.text)
            else:
                page_a_num = len(page_div.findAll('a'))
                total_pages = page_a_num - 1 if page_a_num > 2 else page_a_num

            for i in range(total_pages):
                url_page = url + u"/d%s" % (i + 1)
                results.extend(property_spider(url_page))
            #if len(results) > 100:
                #return results

            print('current properties %s %s %s' % (len(results), area[0], sub_area[1]))
    #process_pool.join()
    return results


def trans_spider(url_page):
    """
    爬取页面链接中的小区信息
    """
    #try:
    #print('search %s' % url_page)
    plain_text = do_request(url_page).text
    soup = BeautifulSoup(plain_text, 'lxml')
    # except (urllib2.HTTPError, urllib2.URLError) as e:

    transactions = soup.findAll('div', {'class': 'info'})
    tran_list = list()
    for tran in transactions:

        tran_info = list()
        try:
            trade_time = tran.find('div', {'class':'info-col deal-item main strong-num'}).text
            price = tran.find('div', {'class':'info-col price-item main'}).find('span', {'class':'strong-num'})
            price = price.text
            district_tag = tran.find('span', {'class':'row2-text'}).findAll('a')
            sub_district = district_tag[1].text
            district = district_tag[0].text
            row = tran.find('div', {'class': 'info-row'})
            xiaoqu = row.find('span', {'class': 'cj-text'}).text
            area = re.findall(' (.*)平', row.text)[0]
            room_type = re.findall('\s+(.+室.+厅) ', row.text)[0]
            unit_price = tran.find('div', {'class':'info-col price-item minor'}).text
            unit_price = re.findall('\d+', unit_price)[0]
            info = re.match('\s+(.+)\s+\|?(.*)\s+\|?(.*)', tran.find('div', {'class': 'row1-text'}).text).groups()
            floor = info[0]
            aspect = info[1]
            decoration = info[2]

            href = tran.find('a', {'class': 'info-col text link-hover-green'}).get('href')

            #'小区名字', '大区域', '小区域', '价格'，'交易时间'，'面积'，'房型', '单价', '楼层', '朝向', '装修', 链接'
            tran_info.append(xiaoqu)
            tran_info.append(district)
            tran_info.append(sub_district)
            tran_info.append(price)
            tran_info.append(trade_time)
            tran_info.append(area)
            tran_info.append(room_type)
            tran_info.append(unit_price)
            tran_info.append(floor)
            tran_info.append(aspect)
            tran_info.append(decoration)
            tran_info.append(href)

        except (IndexError, AttributeError):
            print(url_page)
            print(tran.text)
            raise IndexError
        tran_list.append(tran_info)
    return tran_list


@stop_time
def do_trans_spider(big_areas, start=0):
    """
    爬取大区域中的所有小区信息
    """
    xiaoqu_url = u'/chengjiao/'
    #查找大区域
    results = list()
    for area in islice(big_areas.values(), start, len(big_areas)):
        for sub_area in islice(area, 1, len(area)):
            url = Home_url+xiaoqu_url+sub_area[0]

            plain_text = do_request(url).text
            soup = BeautifulSoup(plain_text, 'lxml')
            page_div = soup.find('div', {'class': 'c-pagination'})
            if not page_div:
                print('not find page %s %s' % (area[0], sub_area[0]))
                continue
            total_pages = page_div.find('a', {'gahref': 'results_totalpage'})
            if total_pages:
                total_pages = int(total_pages.text)
            else:
                page_a_num = len(page_div.findAll('a'))
                total_pages = page_a_num - 1 if page_a_num > 2 else page_a_num

            for i in range(total_pages):
                url_page = url + u"/d%s" % (i + 1)
                results.extend(trans_spider(url_page))
            #if len(results) > 100:
                #return results

            print('current transition %s %s %s' % (len(results), area[0], sub_area[1]))

    return results


if __name__ == '__main__':
    login()
    districts = district_spider()

    btrans = False
    bstock = True
    bcommunity = True
    # 成交
    if btrans:
        transitions = do_trans_spider(districts)
        df_transitions = pd.DataFrame(transitions, columns=Transitions_Info_Col)
        df_transitions.to_csv('transitions_%s.csv' % time.strftime("%Y_%m_%d_%H_%M_%S", time.localtime()))

    #在售
    if bstock:
        properties = do_property_spider(districts)
        df_properties = pd.DataFrame(properties, columns=Properties_Info_Col)
        df_properties.to_csv('properties_%s.csv' % time.strftime("%Y_%m_%d_%H_%M_%S", time.localtime()))

    #小区
    if bcommunity:
        communities = do_xiaoqu_spider(districts)
        df_communities = pd.DataFrame(communities, columns=Communities_Info_Col)
        df_communities.to_csv('communities_%s.csv' % time.strftime("%Y_%m_%d_%H_%M_%S", time.localtime()))


