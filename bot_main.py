import tweepy
import serial
from serial.tools import list_ports
import time
import numpy as np
from collections import deque
import csv
import datetime as dt
import os
import tools
import logging
import itertools

class Xbot():
    def __init__(self):
        with open("./TOKENKEY.txt") as f:
            keys = f.readlines()
        self.consumer_key = keys[0].split(":")[-1].strip()
        self.consumer_secret = keys[1].split(":")[-1].strip()
        self.access_token = keys[2].split(":")[-1].strip()
        self.access_token_secret = keys[3].split(":")[-1].strip()
        self.client = tweepy.Client(
            consumer_key = self.consumer_key,
            consumer_secret = self.consumer_secret,
            access_token = self.access_token,
            access_token_secret = self.access_token_secret
        )
    def postTweet(self,txt):
        self.client.create_tweet(text = txt)

class ArduinoManager():
    def __init__(self):
        ports=list_ports.comports()
        #for i in ports:
        #    print(i.description)
        if not len(ports) == 0:
            self.arduino=serial.Serial('/dev/ttyUSB0')
        else:
            print('Ardunoは接続されていません')
    


class DataManager():
    def __init__(self, init_settings):
        self.init_settings = init_settings
        self.startTime = dt.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        os.mkdir(f"Data/{self.startTime}")
        self.arduinoManager = ArduinoManager()
        show_samples = self.init_settings["display_duration"] * self.init_settings["sampling_rate"]
        self.raw_signals = []
        for idx in range(self.init_settings["num_channels"]):
            self.raw_signals.append(deque(np.zeros(show_samples), maxlen=show_samples))
        
    def save_csv(self,raw_signals,settings,save_data_path):
        num_log_samples = settings["log_interval"] * settings["sampling_rate"]
        last_averages = []
        for raw_signal in raw_signals:
            last_average = np.mean(list(raw_signal)[-num_log_samples:])
            last_averages.append(last_average)
        last_averages.insert(0, str(dt.datetime.now()))

        with open(save_data_path, "a") as f:
            writer = csv.writer(f)
            writer.writerow(last_averages)
    
    
    
    def start(self,min):
        i = 0
        try:
            time_sta = time.perf_counter()
            time_tmp = time_sta
            # シリアル通信を受け取り，.csvに記録する処理
            for line in self.arduinoManager.arduino:
                try:
                    line = line.decode().rstrip().split(",")
                    # 文字から数値に変換
                    raw_signal_now = np.array([int(s) for s in line]) * 5 / 1023
                    for idx, raw_signal in enumerate(self.raw_signals):
                        raw_signal.append(raw_signal_now[idx])
                except ValueError:
                    pass
                except IndexError:
                    print("Error: チャンネル数を確認してください。")
                if(time.perf_counter()-time_tmp>= self.init_settings["log_interval"]):
                    time_tmp=time.perf_counter()
                    self.save_csv(self.raw_signals,self.init_settings,f"./Data/{self.startTime}/{self.startTime}.csv")
                if(time.perf_counter()-time_sta>=60*min):break
                
        except serial.SerialException as e:
            if "[Errno 9]" in str(e):
                print("測定を停止しました。")
                pass
            elif "[Errno 6]" in str(e):
                print("Error: USB接続が切れました。記録を停止します。")
        print("１時間経過\n記録完了")
        self.arduinoManager.arduino.close()
        self.csv_path = f"./Data/{self.startTime}"
class DashLoggerHandler(logging.StreamHandler):
    def __init__(self, console):
        logging.StreamHandler.__init__(self)
        self.console = console

    def emit(self, record):
        msg = self.format(record)
        print(msg)
        self.console.append(msg)


# set logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
# FORMAT = "%(asctime)s %(message)s"
FORMAT = "%(message)s"
logging.basicConfig(level=logging.INFO, format=FORMAT)




class DrawGraph:
    colorpalette = itertools.cycle(
        [
            "#636EFA",
            "#EF553B",
            "#00CC96",
            "#AB63FA",
            "#FFA15A",
            "#19D3F3",
            "#FF6692",
            "#B6E880",
            "#FF97FF",
            "#FECB52",
        ]
    )

    def __init__(
        self, _csv_path, _settings, _measurement_settings
    ) -> None:
        # init variables
        self.csv_path = _csv_path
        self.settings = _settings
        self.measurement_settings = _measurement_settings
        self.init_variables(self.settings, self.measurement_settings)

        # Draw Figure
        self.data = self.plot(True)

    def init_variables(self, _settings, _measurement_settings):
        self.pre_max_time = self.pre_min_time = dt.datetime.strptime(
            _settings["start_date"], "%Y-%m-%d_%H-%M-%S"
        )
        sample_freq = 1 / float(_measurement_settings["log_interval"])
        self.num_load_samples = int(_settings["num_load_hours"] * 60 * 60 * sample_freq)
        self.data_arr: dict[str, deque] = {
            "date": deque([], maxlen=self.num_load_samples),
            "raw": deque([], maxlen=self.num_load_samples),
            "filtered": deque([], maxlen=self.num_load_samples),
            # "HPF": deque([], self.num_load_samples),
        }
        self.line_loaded = 0

        # )

    def plot(self, _init_call_flg):
        # main
        t1 = time.time()
        logger.info("########\nfile loading...")
        with open(self.csv_path) as f:
            # 読み込み制限
            raw_data = f.readlines()  ## ファイルを全行読む
            new_data = (
                raw_data[-self.num_load_samples :]  ## 初回読み込みの場合は制限の分だけ読む
                if _init_call_flg
                else raw_data[self.line_loaded :]  ## 初回以外の読み込みの場合は未読み込みの部分だけ読む
            )
            self.line_loaded = len(raw_data)

            # 最終行のNULLを削除
            if 0 < len(new_data) and "\0" in new_data[-1]:
                new_data = new_data[0:-1]

            # 読み込み
            for row in csv.reader(new_data):
                if(len(row)>0):
                    ### date
                    try:
                        date: int = int(
                            dt.datetime.strptime(
                                str(row[0]), "%Y-%m-%d %H:%M:%S.%f"
                            ).timestamp()
                        )
                    except:
                        date: int = int(
                            dt.datetime.strptime(
                                str(row[0]), "%Y-%m-%d %H:%M:%S"
                            ).timestamp()
                        )
                    self.data_arr["date"].append(date)
    
                    ### value
                    value: float = float(row[1 + self.settings["channel"]])
                    if self.settings["invert_flg"]:
                        value: float = float(5 - value)
                    self.data_arr["raw"].append(value)
    
                    ### filtered LPF
                    k: float = self.settings["LPF_strength"]
                    value_filtered: float = (
                        k * self.data_arr["filtered"][-1] + (1 - k) * value
                        if 0 < len(self.data_arr["filtered"])
                        else value
                    )
                    self.data_arr["filtered"].append(value_filtered)
    
                    ### filtered HPF
                    # k: float = self.settings["LPF_strength"]
                    # value_HPF: float = (
                    #     0.999
                    #     * (self.data_arr["HPF"][-1] + value - self.data_arr["raw"][-2])
                    #     if 0 < len(self.data_arr["HPF"])
                    #     else 0
                    # )
                    # self.data_arr["HPF"].append(value_HPF)
        return self.data_arr["filtered"]


class Filter():
    
    def __init__(self, _folder_path,settings,measurement_settings):
            super(Filter, self).__init__()
            # paths
            self.csv_path: str = tools.get_csv_path(_folder_path)
            # settings
            self.settings = settings
            self.measurement_settings = measurement_settings
            # graph
            self.graph = DrawGraph(
                self.csv_path,
                self.settings,
                self.measurement_settings,
            )


if __name__ == "__main__":
    hiragana = "ぁあぃいぅうぇえぉおかがきぎくぐけげこごさざしじすずせぜそぞただちぢっつづてでとどなにぬねのはばぱひびぴふぶぷへべぺほぼぽまみむめもゃやゅゆょよらりるれろゎわゐゑをんゔゕゖ"
    init_settings = {
        "sampling_rate": 100,
        "log_interval": 1,
        "num_channels": 1,
        "display_duration": 5,
        "place": "家",
        "temperature": 20.0,
        "humidity": 50,
        "plant": "オキシカルディウム",
        "purpose": "",
        "note": "",
    }
    analysis_settings = {
        "channel": 0,
        "start_date": "2023-08-30_17-40-00",
        "invert_flg": False,
        "num_load_hours": 1,
        "LPF_strength": 0.8,
        "on_threshold": 0.03,
        "off_threshold": 0.03,
        "update_flg": True,
        "update_seconds": 10,
    }
    data = DataManager(init_settings)
    data.start(180)
    #data.start(10)
    tmpfilter = Filter(data.csv_path,analysis_settings,init_settings)
    #tmpfilter = Filter("Data/2023-08-31_11-29-10",analysis_settings,init_settings)
    filteredList = list(tmpfilter.graph.plot(True))
    minlist = []
    tmpsum = 0
    for i in range(len(filteredList)):
        tmpsum+=float(filteredList[i])
        if(i%60==0):
            minlist.append(tmpsum/60)
            tmpsum=0
    minlist = minlist[2:]
    filternp = np.array(minlist)
    th = (filternp.max()+filternp.min())/2
    message = ""
    for i in range(len(minlist)):
        if(i!=len(minlist)-1):
            if(filternp[i]<=th and filternp[i+1]>=th) or (filternp[i]>=th and filternp[i+1]<=th):
                message+=hiragana[int(i*86/len(minlist))]
    print(message)
    bot = Xbot()
    bot.postTweet(message)
    