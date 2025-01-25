import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import holidays
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
import os
from Model.gcmd_mxier import MVMD


def get_point_df(flows,climate,point):
    days_flow=np.zeros(shape=(59,288))
    for k in range(9):
        for i in range(7*k,min(7*(k+1),59)):
            day=i
            data=flows[:,point,0][288*day:288*(day+1)]
            data=data.astype(np.float64)
            days_flow[i]=data
    weekday=[]
    saturday=[]
    sunday=[]
    holiday=[]
    holiday_list=[0,14,49]
    for i in range(59):
        dayi=days_flow[i]
        dayi_array = np.array(dayi).reshape(-1)  
        if(i in holiday_list):
            holiday.append(dayi_array)
        else:
            if(i%7==5):
                saturday.append(dayi_array)
            elif(i%7==6):
                sunday.append(dayi_array)
            else:
                weekday.append(dayi_array)
    saturday=np.array(saturday)
    sunday=np.array(sunday)
    weekday=np.array(weekday)
    holiday=np.array(holiday)

    def outliers_nan(arr):
        mean = np.mean(arr,axis=0)
        std =np.std(arr,axis=0)
        arr[np.abs(arr - mean) > 2 * std] = np.nan
        return arr 
    
    saturday=outliers_nan(saturday)
    sunday=outliers_nan(sunday)
    weekday=outliers_nan(weekday)
    holiday=outliers_nan(holiday)
    
    saturday_avg=np.zeros(288)
    sunday_avg=np.zeros(288)
    weekday_avg=np.zeros(288)
    holiday_avg=np.zeros(288)
    for i in range(288):
        not_nan_num=0
        not_nan_sum=0
        for j in range(40):
            arr=weekday[j]
            if not np.isnan(arr[i]):
                not_nan_sum+=arr[i]
                not_nan_num+=1
        weekday_avg[i]=not_nan_sum/not_nan_num
        
    for i in range(288):
        not_nan_num=0
        not_nan_sum=0
        for j in range(8):
            arr=sunday[j]
            if not np.isnan(arr[i]):
                not_nan_sum+=arr[i]
                not_nan_num+=1
        sunday_avg[i]=not_nan_sum/not_nan_num
        
    for i in range(288):
        not_nan_num=0
        not_nan_sum=0
        for j in range(8):
            arr=saturday[j]
            if not np.isnan(arr[i]):
                not_nan_sum+=arr[i]
                not_nan_num+=1
        saturday_avg[i]=not_nan_sum/not_nan_num   
        
    for i in range(288):
        not_nan_num=0
        not_nan_sum=0
        for j in range(3):
            arr=holiday[j]
            if not np.isnan(arr[i]):
                not_nan_sum+=arr[i]
                not_nan_num+=1
        holiday_avg[i]=not_nan_sum/not_nan_num  
    def nan_processing(data,avg):
        for i in range(288):
            if  np.isnan(data[i]):
                    data[i]=avg[i]
        return data
    
    for i in range(59):
        dayi=days_flow[i]
        dayi_array = np.array(dayi).reshape(-1)  
        if(i in holiday_list):
            dayi=nan_processing(dayi,holiday_avg)
        else:
            if(i%7==5):
                dayi=nan_processing(dayi,saturday_avg)
            elif(i%7==6):
                dayi=nan_processing(dayi,sunday_avg)
            else:
                dayi=nan_processing(dayi,weekday_avg)    
        days_flow[i]=dayi

    for i in range(len(weekday)):
        dayi=weekday[i]
        dayi_array = np.array(dayi).reshape(-1)  
        weekday[i]=nan_processing(dayi,weekday_avg)
    for i in range(len(saturday)):
        dayi=saturday[i]
        dayi_array = np.array(dayi).reshape(-1)  
        saturday[i]=nan_processing(dayi,saturday_avg)
    for i in range(len(sunday)):
        dayi=sunday[i]
        dayi_array = np.array(dayi).reshape(-1)  
        sunday[i]=nan_processing(dayi,sunday_avg)
    for i in range(len(holiday)):
        dayi=holiday[i]
        dayi_array = np.array(dayi).reshape(-1)  
        holiday[i]=nan_processing(dayi,holiday_avg)
    
    alldays=[]
    for i in range(14,59):
        for j in range(288):
            alldays.append(days_flow[i][j])

    def get_time_list(start,end,interval= 5):
        start_time = datetime.strptime(start, '%Y-%m-%d %H:%M:%S')
        end_time = datetime.strptime(end, '%Y-%m-%d %H:%M:%S')
        delta = timedelta(minutes=interval)
        time_list = []
        while start_time <= end_time:
            time_list.append(start_time.strftime('%Y-%m-%d %H:%M:%S'))
            start_time += delta
        return(time_list)
    timelist=get_time_list('2018-01-15 00:00:00','2018-02-28 23:55:00',interval=5)
    data = {"ds": timelist, "y": alldays}
    flow_df = pd.DataFrame(data)
    flow_df['ds'] = pd.to_datetime(flow_df['ds'])
    flow_df['time_month']=flow_df['ds'].apply(lambda x: x.month)
    flow_df['time_day']=flow_df['ds'].apply(lambda x: x.day)
    flow_df['time_hour']=flow_df['ds'].apply(lambda x: x.hour)
    flow_df['time_minute']=flow_df['ds'].apply(lambda x: x.minute//5)
    flow_df['week']=flow_df['ds'].apply(lambda x: x.dayofweek)
    flow_df['weekend']=flow_df['week'].apply(lambda x:0 if x<5 else 1)
    holiday_us=holidays.US(years=2018)
    flow_df['holiday']=flow_df['ds'].apply(lambda x: 1 if x in holiday_us else 0)
    flow_df['weekend'] = flow_df.apply(lambda x: 1 if x['holiday'] == 1 else x['weekend'], axis=1)
    flow_df['week'] = flow_df.apply(lambda x: 10 if x['holiday']==1 else x['week'], axis=1)


    flow_df.drop(['ds'],axis=1,inplace=True)

    def time_num(df):
        df['time_num']=df['time_hour']*60+df['time_minute']*5
        return df

    def ls1(item):
        dayi=int(item.name//288)+14
        if dayi==14:
            return holiday[0][int(item['time_num']//5)]
        elif dayi==49:
            return holiday[1][int(item['time_num']//5)]
        elif item['week']==5:
            return saturday[int(dayi//7)-1][int(item['time_num']//5)]
        elif item['week']==6:
            return sunday[int(dayi//7)-1][int(item['time_num']//5)]
        else:
            if dayi==21 or dayi==56:
                return days_flow[dayi-14][int(item['time_num']//5)]
            else:
                return days_flow[dayi-7][int(item['time_num']//5)]
    def ls2(item):
        dayi=int(item.name//288)+14
        if dayi==14:
            return holiday[0][int(item['time_num']//5)]
        elif dayi==49:
            return holiday[1][int(item['time_num']//5)]
        elif item['week']==5:
            return saturday[int(dayi//7)-2][int(item['time_num']//5)]
        elif item['week']==6:
            return sunday[int(dayi//7)-2][int(item['time_num']//5)]
        else:
            if dayi==21 or dayi==56:
                return days_flow[dayi-21][int(item['time_num']//5)]
            else:
                return days_flow[dayi-14][int(item['time_num']//5)]        



    def yesterday(item):
        return days_flow[int(item.name//288)+13][int(item['time_num']//5)]
    
    climate_repeat=pd.concat([pd.DataFrame(climate.iloc[14]).T]*288,ignore_index=True,axis=0)
    for i in range(15,59):
        climate_I=pd.concat([pd.DataFrame(climate.iloc[i]).T]*288,ignore_index=True,axis=0)
        climate_repeat=pd.concat([climate_repeat,climate_I],ignore_index=True,axis=0)
    flow_df=time_num(flow_df)
    flow_df['point']=point
    flow_df=pd.concat([flow_df,climate_repeat],axis=1)
    flow_df['yes']=flow_df.apply(yesterday, axis=1)
    flow_df['ls1']=flow_df.apply(ls1, axis=1)
    flow_df['ls2']=flow_df.apply(ls2, axis=1)

    return flow_df


def get_pems04_data():
    pems04=np.load('./Datasets/pems04/pems04.npz')
    climate=pd.read_csv("./Datasets/pems04/climate04.csv")
    return pems04, climate


class Pems04_Dataset(Dataset):
    def __init__(self,config,mode=0):
        # mode:0:all，mode:1 train，mode:2 val，mode:3 test
           
        alpha=config["alpha"]
        tau=config["tau"]
        K=config["K"]
        DC=config["DC"]
        init=config["init"]
        tol=config["tol"]
        max_N=config["max_N"]

        path = (
            "./DataProcess/pems04_process_result/Pems04_alpha" + str(alpha) +'_tau'+str(tau)+ "_K" + str(K) +'_DC'+str(DC)+'_init'+str(init)+'_tol'+str(tol)+'_max_N'+str(max_N)+ ".csv"
        )

        if os.path.isfile(path) == False:
            pems04, climate = get_pems04_data()

            all_point_df=get_point_df(pems04['data'],climate,0)
            for i in range(1,307):
                pointi_df=get_point_df(pems04['data'],climate,i)
                all_point_df=pd.concat([all_point_df,pointi_df],ignore_index=True,axis=0)
            yll=all_point_df[['yes','ls1','ls2']]
            yll_t=torch.tensor(yll.values).reshape(307,45,288,3).permute(1,3,0,2)
            device = torch.device(config['device'])
            mvmd=MVMD(alpha, tau, K, DC, init, tol, max_N).to(device)
            md=torch.zeros([45,3,307,288]).to(device)
            for i in range(45):
                for j in range(3):
                    u,_,_=mvmd(yll_t[i][j].to(device))
                    md[i][j]=u[0].permute(1,0)
            md=md.permute(2,0,3,1).reshape(-1,3).cpu().detach().numpy()
            md_df = pd.DataFrame(md,columns=['yes_v','ls1_v','ls2_v'])
            df=pd.concat([all_point_df,md_df],axis=1)
            df.to_csv(path,sep=',',index=False,header=True) 
        else :
            df=pd.read_csv(path)

        df=df.drop(['time_day','time_month','time_num','Day','SLP','H','VV','V','VM','VG','SN','TS','PP','T','TM','Tm','FG'],axis=1)


        train_index=[0,31*288]
        valid_index=[31*288,38*288]
        test_index=[38*288,45*288]
        if mode==1:
            use_index_list=train_index
        elif mode==2:
            use_index_list=valid_index
        elif mode==3:
            use_index_list=test_index
        elif mode==0:
            use_index_list=[0,45*288]



        feature=df.drop(['y'],axis=1).values
        flow=df['y'].values

        feature=feature.reshape(307,288*45,13)
        flow=flow.reshape(307,288*45)


        train_X = feature[:,train_index[0]:train_index[1],:].reshape(-1,13)
        train_y = flow[:,train_index[0]:train_index[1]].reshape(-1,1)
        max_x=np.max(train_X,axis=0)
        min_x=np.min(train_X,axis=0)
        self.max=np.max(train_y,axis=0)
        self.min=np.min(train_y,axis=0)

        feature=(feature.reshape(-1,13)-min_x)/(max_x-min_x+1e-9)
        flow=(flow.reshape(-1,1)-self.min)/(self.max-self.min+1e-9)
        feature=feature.reshape(307,288*45,13)
        flow=flow.reshape(307,288*45)

        self.data_x=feature[:,use_index_list[0]:use_index_list[1],:]
        self.data_y=flow[:,use_index_list[0]:use_index_list[1]]

    def __getitem__(self, index):
        # index = self.use_index_list[org_index]
        start = index*288
        end = (index+1)*288
        x=torch.tensor(self.data_x[:,start:end,:10],dtype=torch.float32)
        md=torch.tensor(self.data_x[:,start:end,10:],dtype=torch.float32)
        y=torch.tensor(self.data_y[:,start:end],dtype=torch.float32)
        return x,md,y

    def __len__(self):
        return len(self.data_y[0])//288
    
    def get_max_min(self):
        return self.max, self.min
    



def get_dataloader(config, batch_size=16):

    dataset = Pems04_Dataset(config,mode=1)
    max,min=dataset.get_max_min()
    train_loader = DataLoader(dataset, batch_size=batch_size, shuffle=1)
    valid_dataset = Pems04_Dataset(config,mode=2)
    valid_loader = DataLoader(valid_dataset, batch_size=batch_size, shuffle=0)
    test_dataset = Pems04_Dataset(config,mode=3)
    test_loader = DataLoader(test_dataset, batch_size=batch_size, shuffle=0)
    
    return train_loader, valid_loader, test_loader,max,min