import numpy as np, pandas as pd, yaml, os, pytz, re
from datetime import datetime
from collections import defaultdict


class ConfigLoader:
    def __init__(self, config_path_sensors, config_path_sensors_properties):
        self.config_path = config_path_sensors
        self.config_path_sensors_properties = config_path_sensors_properties
        self.sensor_details = {}
        self.path = ''
        self.config, self.config_sensor_properties = self._read_config()
        # print(self.config_sensor_properties)

    def _read_config(self):
        with open(self.config_path, 'r') as file:
            config = yaml.safe_load(file)
            self.path = config['dataset']['path']
            self.sensor_details = config['sensors']
            # self.sensors_present_at_a_location = config['sensors']

        with open(self.config_path_sensors_properties, 'r') as file:
            config_sensor_properties = yaml.safe_load(file)    

        return config, config_sensor_properties
    

    
    def get_sensor_info(self, sensor_id):
        return self.sensor_details.get(sensor_id, None)        

    def get_sensors_present_at_a_location(self, loc):
        return self.sensors_present_at_a_location.get(loc, None)   

# class DataLoaderTemp:
#     def __init__(self, data_path, config_loader):
#         self.data_path = data_path
#         self.config_loader = config_loader
#         # sensor_info = self.config_loader.get_sensor_info('R1')
#         # print(sensor_info)

#     def f1(self, sensor_id = 'R1'):
#         sensor_info = self.config_loader.get_sensor_info('R1')
#         if sensor_info:
#             print(f"Sensor ID: {sensor_id}")
#             print(f"Sensor Info: {sensor_info}")
#         else:
#             print(f"No information found for sensor ID: {sensor_id}")


class DataLoader:
    def __init__(self, data_path, activity_patterns,config_path, config_loader):
        self.data_path = data_path
        self.config_path = config_path
        self.config_loader = config_loader
        self.activity_patterns  = activity_patterns    
    
    def extract_subject_names(self):
        subject_names = []
        
        for activity_pattern in self.activity_patterns:
            instances = sorted(os.listdir(os.path.join(self.data_path, activity_pattern)))
            
            for instance in instances:
                subjects = sorted(os.listdir(os.path.join(self.data_path, activity_pattern, instance)))
                
                for subject in subjects:
                    if subject != 'environmental.csv':
                        subject_names.append(subject)
    
        return sorted(set(subject_names))
    
    def arrange_sensor_events(self,df):
        """
        Extracts ON and OFF events for sensors from the given DataFrame.

        Parameters:
        df (pd.DataFrame): Input DataFrame containing sensor data with columns 'sensor_id', 'sensor_status', 'ts', and 'subject_id'.

        Returns:
        pd.DataFrame: DataFrame containing associated sensor_id, ON and OFF timestamps, and corresponding subject_ids.
        """
        # Dictionary to store ON timestamps and corresponding subject_ids for each sensor
        onTimestamps = {}
        onSubjectIds = {}

        # Lists to store associated sensor_id, ON and OFF timestamps, and corresponding subject_ids
        sensorIds = []
        onTimes = []
        offTimes = []
        onSubjects = []
        offSubjects = []
        
        # sensor_ids_without_off = set(df[df['sensor_status'] == 'ON']['sensor_id']) - set(df[df['sensor_status'] == 'OFF']['sensor_id'])
        # Step 1: Identify sensor_ids without corresponding 'OFF' event
        sensor_ids_without_off = set(df[df['sensor_status'] == 'ON']['sensor_id']) - set(df[df['sensor_status'] == 'OFF']['sensor_id'])
        max_val = df['ts'].max()

        # Step 2 and 3: Add missing 'OFF' events
        for sensor_id in sensor_ids_without_off:
            # Find the corresponding 'ON' event with the maximum timestamp and the same subject_id
            max_ts_row = df[(df['sensor_id'] == sensor_id) & (df['sensor_status'] == 'ON')].nlargest(1, 'ts')
            
            if not max_ts_row.empty:
                max_ts_value = max_ts_row['ts'].values[0]
                subject_id = max_ts_row['subject_id'].values[0]
                
                # Add a new row for the missing 'OFF' event
                new_row = {'sensor_id': sensor_id, 'sensor_status': 'OFF', 'ts':max_val , 'subject_id': subject_id}
                # df = df.append(new_row, ignore_index=True)
                df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)

        
        # Iterate through the DataFrame rows
        for index, row in df.iterrows():
            sensor_id = row['sensor_id']
            status = row['sensor_status']
            timestamp = row['ts']
            subject_id = row['subject_id']
            
            # print(sensor_id, '\t', status, '\t', subject_id)
            # If status is "ON", update the ON timestamp and corresponding subject_id for the sensor
            if status == 'ON':
                # print('hi')
                onTimestamps[sensor_id] = timestamp
                onSubjectIds[sensor_id] = subject_id
            elif status == 'OFF' and sensor_id in onTimestamps:
                # print('bye')
                sensorIds.append(sensor_id)
                onTimes.append(onTimestamps[sensor_id])
                offTimes.append(timestamp)
                onSubjects.append(onSubjectIds[sensor_id])
                offSubjects.append(subject_id)
            else:
                pass
                # print('ciao')
            
        # Create a new DataFrame with associated sensor_id, ON and OFF timestamps, and corresponding subject_ids
        associatedDf = pd.DataFrame({
            'sensor_id': sensorIds,
            'ts_start': onTimes,
            'ON_subject_id': onSubjects,
            'ts_end': offTimes,
            'OFF_subject_id': offSubjects
        })
        
        return associatedDf


    def load_environmental_sensor_data(self, instance_folder_path, subject_folder_path):
        ## Load the environmental.csv
        envDf = pd.read_csv(os.path.join(instance_folder_path, 'environmental.csv'))
        ## Arrange sensor in [sensor_id, ts_start, on_subject, ts_end, off_subject] dataframe format
        arrangedDfOnOffEnv = self.arrange_sensor_events(envDf)    
        ## Extract subject_id from subjectFolder name Example: Extract 200 from 'subject-200'
        subjectId = int(subject_folder_path.split('-')[1])
        arrangedDfOnOffEnv = arrangedDfOnOffEnv[(arrangedDfOnOffEnv['ON_subject_id'] == subjectId)]
        minimumTimestampOnOffEnv = arrangedDfOnOffEnv['ts_start'].min() # 1542203894445
        return arrangedDfOnOffEnv, minimumTimestampOnOffEnv
    
    def load_labels_data(self, subject_folder_path):
        ## Load labels.csv
        label_df = pd.read_csv(os.path.join(subject_folder_path, 'labels.csv'))
        ## Make a copy of label file
        label_df_new = label_df.copy()
        return label_df, label_df_new    

    def load_locations_data(self,subject_folder_path):
        ## Find location information with respect to a subject
        location_df = pd.read_csv(os.path.join(subject_folder_path, 'locations.csv'))
        # Sort the DataFrame by 'ts_end' - 'ts_start' (window size) in descending order
        location_df['window_size'] = location_df['ts_end'] - location_df['ts_start']
        location_df = location_df.sort_values(by='window_size', ascending=False)
        # Drop duplicates based on 'ts_start', keeping the first occurrence (highest window size)
        location_df = location_df.drop_duplicates(subset=['ts_start'], keep='first')
        # Drop the 'window_size' column if it's not needed in the final result
        location_df = location_df.drop('window_size', axis=1)
        location_df = location_df.sort_values(by='ts_start', ascending=True)
        location_df_new = location_df
        # convert dataframe into numpy array
        location_df  = location_df.values
        # Minimum time in the window, it will help in creating window
        minimumTimestampLocation = np.min(location_df[:,0])
        # Maximum time in the window, it will help in stopping the loop
        maximumTimestampLocation = np.max(location_df[:,1])
        # Select minimum start time from both (environmental.csv and location.csv)
        return location_df, location_df_new, minimumTimestampLocation, maximumTimestampLocation

    def arrange_smartphone_events(self,df):    
        # Sample DataFrame (replace this with your actual DataFrame)
        # df = pd.DataFrame({
        #     'sensor_id': ['S1', 'S1', 'S2', 'S2', 'S1', 'S1', 'S3', 'S3'],
        #     'sensor_status': ['ON', 'OFF', 'ON', 'OFF', 'ON', 'OFF', 'ON', 'OFF'],
        #     'ts': [1543316232000, 1543316315000, 1543316233000, 1543316235000,
        #            1543316239000, 1543316315099, 1543316233000, 1543316235000]
        # })
        
        onTimestamps = {}
        sensorIds = []
        onTimes = []
        offTimes = []
        
        # Iterate through the DataFrame rows
        for index, row in df.iterrows():
            sensor_id = row['event_id']
            status = row['event_status']
            timestamp = row['ts']
            
            # If status is "ON", update the ON timestamp for the sensor
            if status == 'ON':
                onTimestamps[sensor_id] = timestamp
            elif status == 'OFF' and sensor_id in onTimestamps:
                sensorIds.append(sensor_id)
                onTimes.append(onTimestamps[sensor_id])
                offTimes.append(timestamp)
        
        # Create a new DataFrame with associated sensor_id, ON and OFF timestamps
        associatedDf = pd.DataFrame({
            'event_id': sensorIds,
            'ts_ON': onTimes,
            'ts_OFF': offTimes,
        })
        
        # print(associatedDf)
        return associatedDf

    def load_smartphone_data(self, subject_folder_path):
        ## Define a flag variable to check whether the smartphone.csv is empty or  not
        ## if smartphone.csv is empty then create, then create a dummy dataframe and set flat = 1
        flag = 0
        try:
            smartphone_df = pd.read_csv(os.path.join(subject_folder_path, 'smartphone.csv'))
            if not smartphone_df.empty:
                arrangedSmartphone = self.arrange_smartphone_events(smartphone_df)
                minimumTimestampSmart = arrangedSmartphone['ts_ON'].min()
                return arrangedSmartphone, minimumTimestampSmart , flag
            else:
                # Make a dummy dataframe
                dta = {'event_id': ['S99'], 'ts_ON': [-5], 'ts_OFF': [-10]}
                arrangedSmartphone = pd.DataFrame(dta)
                minimumTimestampSmart = np.inf
                flag = 1
                return arrangedSmartphone, minimumTimestampSmart , flag
        except pd.errors.EmptyDataError:
            # Make a dummy dataframe
            dta = {'event_id': ['S99'], 'ts_ON': [-5], 'ts_OFF': [-10]}
            arrangedSmartphone = pd.DataFrame(dta)
            minimumTimestampSmart = np.inf
            flag = 1
            return arrangedSmartphone, minimumTimestampSmart, flag

    def filter_locations_in_window_v2(self, df, window):  
        # print('-+'*50)
        a, b = window
        kk = 0
        ## Extract the overlapping rows with windows
        temp2 = df.values
        common_indices = []
        common_rows = []
        for i in range(len(temp2)):
            ls = temp2[i][0]
            le = temp2[i][1]
            if a <= le and ls <= b:
                common_indices.append(i)
                common_rows.append(temp2[i])
        columns = ['ts_start', 'ts_end', 'location'] 
        filtered_rows = pd.DataFrame(common_rows, columns=columns)
        
        ## Reset the start and end time according to the window
        if filtered_rows.empty:
            # print('Filtered label rows are empty.....')
            return [] , -99 # Return an empty list if there are no rows

        output = []
        for row_idx in range(len(common_indices)):
            # print(row_idx, df.loc[row_idx])
            A = filtered_rows.loc[row_idx, 'ts_start']
            B = filtered_rows.loc[row_idx, 'ts_end']
            activity_name = filtered_rows.loc[row_idx, 'location'] # name of the location
            temp = {'Location':activity_name, 't1':A, 't2':B, 'window start':a ,'window end':b}
            # # Case identification for the current row
            # if A <= a and b <= B:
            #     temp = {'Location':activity_name, 't1':a, 't2':b, 'window start':a ,'window end':b}
            #     kk = 0
            #     case = "Lable Case 1: [a, b] is in between [A, B]"
                
            # elif a < A and b > B:
            #     case = "Case 2: a is less than A and b is greater than B"
            #     temp = {'Location':activity_name, 't1':A, 't2':B, 'window start':a ,'window end':b}
            #     kk = 0
                
            # elif A <= a <= B and b > B:
            #     case = "Case 3: a is in between [A, B] but b > B"
            #     temp = {'Location':activity_name, 't1':a, 't2':B, 'window start':a ,'window end':b}
            #     kk = 0
            # elif a < A and A <= b <= B:
            #     case =  "Case 4: a < A but b is in between [A, B]"
            #     temp = {'Location':activity_name, 't1':A, 't2':b, 'window start':a ,'window end':b}
            #     kk = 0
            # else:
            #     case = "No matching case"    
            output.append(temp)
        return output, kk    ## heloo


    def filter_labels_in_window_v2(self, df, window):
        # print('-*'*50)
        a, b = window
        kk = 0

        temp2 = df.values
        common_indices = []
        common_rows = []
        for i in range(len(temp2)):
            ls = temp2[i][0]
            le = temp2[i][1]
            if a <= le and ls <= b:
                common_indices.append(i)
                common_rows.append(temp2[i])
        columns = ['ts_start', 'ts_end', 'act'] 
        filtered_rows = pd.DataFrame(common_rows, columns=columns)    
                
        if filtered_rows.empty:
            return [] , -99 # Return an empty list if there are no rows

        output = []
        for row_idx in range(len(common_indices)):
            # print(row_idx, df.loc[row_idx])
            A = filtered_rows.loc[row_idx, 'ts_start']
            B = filtered_rows.loc[row_idx, 'ts_end']
            activity_name = filtered_rows.loc[row_idx, 'act']
            temp = {'Label':activity_name, 't1':A, 't2':B, 'window start':a ,'window end':b}
            # # Case identification for the current row
            # if A <= a and b <= B:
            #     temp = {'Label':activity_name, 't1':a, 't2':b, 'window start':a ,'window end':b}
            #     kk = 0
            #     case = "Lable Case 1: [a, b] is in between [A, B]"
                
            # elif a < A and b > B:
            #     case = "Case 2: a is less than A and b is greater than B"
            #     temp = {'Label':activity_name, 't1':A, 't2':B, 'window start':a ,'window end':b}
            #     kk = 0
                
            # elif A <= a <= B and b > B:
            #     case = "Case 3: a is in between [A, B] but b > B"
            #     temp = {'Label':activity_name, 't1':a, 't2':B, 'window start':a ,'window end':b}
            #     kk = 0
            # elif a < A and A <= b <= B:
            #     case = "Case 4: a < A but b is in between [A, B]"
            #     temp = {'Label':activity_name, 't1':A, 't2':b, 'window start':a ,'window end':b}
            #     kk = 0
            # else:
            #     case = "No matching case"    
            output.append(temp)
        return output, kk


    def filter_sensors_in_window_v2(self, df, window):
        # print('-%'*50)
        df = df.sort_values(by='ts_start')
        a, b = window
        kk = -99

        temp2 = df.values
        common_indices = []
        common_rows = []
        for i in range(len(temp2)):
            ls = temp2[i][1]
            le = temp2[i][3]
            if a <= le and ls <= b:
                common_rows.append(temp2[i])
                common_indices.append(i)
        columns = ['sensor_id', 'ts_start', 'ON_subject_id', 'ts_end', 'OFF_subject_id']  
        filtered_rows = pd.DataFrame(common_rows, columns=columns)
            
        if filtered_rows.empty:
            return [] , -99 # Return an empty list if there are no rows
        
        output = []
        for row_idx in range(len(common_indices)):
            # print(row_idx, df.loc[row_idx])
            A = filtered_rows.loc[row_idx, 'ts_start']
            B = filtered_rows.loc[row_idx, 'ts_end']
            activated_sensor = filtered_rows.loc[row_idx, 'sensor_id']
            
            # configLoader = ConfigLoader('/home/hubble/work/project_generalization/src/parameters.yaml')
            sensor_type = 'dummy'#sensor_type_dict.get(activated_sensor)
            sensor_device = 'dummy'#sensor_device_dict.get(activated_sensor)
            sensor_room = 'dummy'#sensor_room_dict.get(activated_sensor)
            temp = {'Sensor':activated_sensor, 't1':A, 't2':B, 'window start':a ,'window end':b}
            # # Case identification for the current row
            # if A <= a and b <= B:
            #     # temp = {'Sensor':activated_sensor, 'window start':a, 'window end':b, 'a':a ,'b':b}
            #     temp = {'Sensor':activated_sensor, 't1':a, 't2':b, 'window start':a ,'window end':b, 'sensor_type': sensor_type, 'sensor_device': sensor_device, 'sensor_room':sensor_room}
            #     kk = 0
            #     case = "Case 1: [a, b] is in between [A, B]"
                
            # elif a < A and b > B:
            #     case = "Case 2: a is less than A and b is greater than B"
            #     temp = {'Sensor':activated_sensor, 't1':A, 't2':B, 'window start':a ,'window end':b, 'sensor_type': sensor_type, 'sensor_device': sensor_device, 'sensor_room':sensor_room}
            #     kk = 0
                
            # elif A <= a <= B and b > B:
            #     case = "Case 3: a is in between [A, B] but b > B"
            #     temp = {'Sensor':activated_sensor, 't1':a, 't2':B, 'window start':a ,'window end':b, 'sensor_type': sensor_type, 'sensor_device': sensor_device, 'sensor_room':sensor_room}
            #     kk = 0
            # elif a < A and A <= b <= B:
            #     case = "Case 4: a < A but b is in between [A, B]"
            #     temp = {'Sensor':activated_sensor, 't1':A, 't2':b, 'window start':a ,'window end':b, 'sensor_type': sensor_type, 'sensor_device': sensor_device, 'sensor_room':sensor_room}
            #     kk = 0
            # else:
            #     case = "No matching case"    
            output.append(temp)
        return output, kk


    def filter_smartphone_in_window_v2(self, df, window):
        # print('-/\-'*50)
        a, b = window
        kk = 0

        temp2 = df.values
        common_indices = []
        common_rows = []
        
        for i in range(len(temp2)):
            ls = temp2[i][1]
            le = temp2[i][2]
            if a <= le and ls <= b:
                common_indices.append(i)
                common_rows.append(temp2[i])
        columns = ['event_id', 'ts_ON', 'ts_OFF'] 
        filtered_rows = pd.DataFrame(common_rows, columns=columns)        
        if filtered_rows.empty:
            return [] , -99 # Return an empty list if there are no rows

        output = []
        for row_idx in range(len(common_indices)):
            # print(row_idx, df.loc[row_idx])
            A = filtered_rows.loc[row_idx, 'ts_ON']
            B = filtered_rows.loc[row_idx, 'ts_OFF']
            event_id = filtered_rows.loc[row_idx, 'event_id']
            temp = {'event_id':event_id, 't1':A, 't2':B, 'window start':a ,'window end':b}

            # # Case identification for the current row
            # if A <= a and b <= B:
            #     temp = {'event_id':event_id, 't1':a, 't2':b, 'window start':a ,'window end':b}
            #     kk = 0
            #     case = "Lable Case 1: [a, b] is in between [A, B]"
                
            # elif a < A and b > B:
            #     case = "Case 2: a is less than A and b is greater than B"
            #     temp = {'event_id':event_id, 't1':A, 't2':B, 'window start':a ,'window end':b}
            #     kk = 0
                
            # elif A <= a <= B and b > B:
            #     case = "Case 3: a is in between [A, B] but b > B"
            #     temp = {'event_id':event_id, 't1':a, 't2':B, 'window start':a ,'window end':b}
            #     kk = 0
            # elif a < A and A <= b <= B:
            #     case =  "Case 4: a < A but b is in between [A, B]"
            #     temp = {'event_id':event_id, 't1':A, 't2':b, 'window start':a ,'window end':b}
            #     kk = 0
            # else:
            #     case = "No matching case"    

            output.append(temp)
        return output, kk   



    def extract_data_from_csv(self,location_df_new,smartphone_df,sensor_on_off_df,label_df, activity_pattern, instance, subject):
        samplesPerPick = 16000
        overlap = .8

        arranged_loc_data = location_df_new.sort_values(by='ts_start' )
        arranged_env_data = sensor_on_off_df.sort_values(by='ts_start')
        arranged_label_data = label_df.sort_values(by='ts_start')
        arranged_phone_data = smartphone_df.sort_values(by='ts_ON')
        arranged_phone_data = arranged_phone_data.drop(arranged_phone_data[arranged_phone_data['event_id'] == 'S99'].index)
        
        if len(arranged_phone_data) == 0:
            min_phone_data = np.inf
            max_phone_data = -np.inf
        else:
            min_phone_data = arranged_phone_data['ts_ON'].min()
            max_phone_data = arranged_phone_data['ts_ON'].max()

        
        min_env_data = arranged_env_data['ts_start'].min()
        min_loc_data = arranged_loc_data['ts_start'].min()
        min_label_data = arranged_label_data['ts_start'].min()

        max_env_data = arranged_env_data['ts_end'].max()
        max_loc_data = arranged_loc_data['ts_end'].max()
        max_label_data = arranged_label_data['ts_end'].max()

        maximum_value = max(max_env_data, max_loc_data, max_phone_data)
        minimum_value = min(min_env_data, min_loc_data, min_phone_data)
        a, b = minimum_value, minimum_value + samplesPerPick  # t_start , t_stop # This is our window of 16 seconds
        
        wind = [] # window
        indx = 0
        while b <= maximum_value:
            # print(indx, '\t', a,'\t',b, '\t', abs(a-b), '\t')
            # ## 80% overlap logic 
            # overlap_size = int(overlap * (b - a))
            # next_window_start = a + (b - a) - overlap_size
            # next_window_end = next_window_start + (b - a)
            # a = next_window_start
            # b = next_window_end
            
    
            location_visited, jj = self.filter_locations_in_window_v2(arranged_loc_data, [a,b])
            sensor_initiated, kk = self.filter_sensors_in_window_v2(arranged_env_data, [a,b])
            label_extracted,ll = self.filter_labels_in_window_v2(arranged_label_data, [a,b])
            if len(arranged_phone_data) > 0:
                phone_initiated, mm = self.filter_smartphone_in_window_v2(arranged_phone_data, [a,b])
            else:
                phone_initiated = []
            # wind.append([location_visited, sensor_initiated, label_extracted, phone_initiated,activity_pattern, instance, subject])
            # wind.append([location_visited, sensor_initiated, label_extracted, phone_initiated,(a,b),(activity_pattern, instance, subject),''])
                
            def merge_phone_initiated_and_sensor_initiated(phone_initiated,sensor_initiated):
                for pi in range(len(phone_initiated)):
                    sensor_initiated.append(phone_initiated[pi])
                return sensor_initiated

            sensor_initiated = merge_phone_initiated_and_sensor_initiated(phone_initiated,sensor_initiated)
            wind.append([location_visited, sensor_initiated,(a,b),label_extracted,(activity_pattern, instance, subject)])                
            # wind.append([location_visited, sensor_initiated,(a,b),label_extracted,(activity_pattern, instance, subject)])
            # obj = Window2Text()
            # aaa = obj.generate_user_questions_version_GITHUB(wind[51])

            # ## 80% overlap logic 
            overlap_size = int(overlap * (b - a))
            next_window_start = a + (b - a) - overlap_size
            next_window_end = next_window_start + (b - a)
            a = next_window_start
            b = next_window_end
            
            ### No overlap logic
            # a = b + 1
            # b = b + 16000
            indx = indx + 1
        return wind

    def subjectwise_windows(self,result_subjects):

        # config_loader = ConfigLoader(self.config_path)
        data_loader = DataLoader(self.data_path, self.activity_patterns, self.config_path, self.config_loader)
        subject_data = {}
        unified_data = []
        for sub in range(len(sorted(result_subjects))):
            subject_name = sorted(result_subjects)[sub]
            subject_id = int(subject_name.split('-')[1]) ## Only numerical value of subject
        
            subject_windowed_data = {}
            ## Pick a subject and look for that subject in each activity pattern

            for ap  in range(len(self.activity_patterns)):
                activity_pattern = self.activity_patterns[ap] #  activity_pattern = activity_patterns[ap]
                ## List the instances in each activity pattern
                instances = sorted(os.listdir(os.path.join(self.data_path, activity_pattern))) ## instances = sorted(os.listdir(os.path.join(data_path, activity_pattern)))
                
                subject_wrt_instance = []
                for ins in range(len(instances)):
                    instance = instances[ins]
                    ## List all the subjects in that particular instance
                    subjects = sorted(os.listdir(os.path.join(self.data_path, activity_pattern, instance))) ## subjects = sorted(os.listdir(os.path.join(data_path, activity_pattern, instance)))
                    
                    ## Read environment.csv
                    if subject_name in subjects:
                        # print('*************')
                        # print(subject_name)
                        # print(os.path.join(self.data_path, activity_pattern, instance))
                        sensor_on_off_df, _ = self.load_environmental_sensor_data(os.path.join(self.data_path, activity_pattern, instance), subject_name) ## sensor_on_off_df, _ = load_environmental_sensor_data(os.path.join(data_path, activity_pattern, instance), subject_name)
                        # print('sensor_on_off_df', '\t\t',sensor_on_off_df, '\n\n')                        

                    ## Load other sensors data
                    for sb in range(len(subjects)):
                        subject = subjects[sb]
                        if subject == subject_name: 
                            # print(activity_pattern, '\t', instance, '\t', subject)
                            subject_path = os.path.join(self.data_path, activity_pattern, instance,subject) ## subject_path = os.path.join(data_path, activity_pattern, instance,subject)
                            # print(subject_path, '\n'*2)
                            label_df, label_df_new = self.load_labels_data(subject_path) ## label_df, label_df_new = load_labels_data(subject_path)
                            # print(label_df, '\n'*2)
                            location_df, location_df_new, _, _ = self.load_locations_data(subject_path) ## location_df, location_df_new, _, _ = load_locations_data(subject_path)
                            # print(location_df_new, '\n'*2)
                            smartphone_df, _, flag = self.load_smartphone_data(subject_path) ## smartphone_df, _, flag = load_smartphone_data(subject_path)
                            # print(smartphone_df, '\n'*2)
                            windd = self.extract_data_from_csv(location_df_new,smartphone_df,sensor_on_off_df,label_df, activity_pattern, instance, subject) ##  windd = extract_data_from_csv(location_df_new,smartphone_df,sensor_on_off_df,label_df, activity_pattern, instance, subject)
                            # unified_data.append(windd)
                            # print(windd[0])
                            # print()
                            # print(windd[1])
                            # print(len(windd))
                            # subject_wrt_instance[instance] = windd
                            subject_wrt_instance.append(windd)
                subject_windowed_data[activity_pattern] = subject_wrt_instance
                # subject_windowed_data.append(subject_wrt_instance)
            subject_windowed_data = {key: value for key, value in subject_windowed_data.items() if value}
            subject_data[subject_name] = subject_windowed_data
            # print('*'*100)
            # print(subject_data)
        return subject_data , unified_data    

class Window2Text:
    def __init__(self, config_path, config_loader, property_loader):
        self.config_loader = config_loader
        self.config_path = config_path
        # print(self.config_loader.config_sensor_properties,'UUUUUUUUU')        

    @staticmethod
    def is_overlap(window1, window2):
        """
        Check if two time windows overlap.
        
        Each window should be a tuple of (start_time, end_time),
        where start_time and end_time are integers representing time.
        """
        start1, end1 = window1
        start2, end2 = window2
        
        # Check for overlap
        if start1 < end2 and start2 < end1:
            return True
        else:
            return False


    ## ws, we, phone_data_t1, phone_data_t2 = ws, we, temp_sens_start, temp_sens_end
    @staticmethod
    def location_sensor_phone_start_end(ws, we, phone_data_t1, phone_data_t2):
        cs = -99
        phone_sentences = ''
        if phone_data_t1 < ws:
            if ws < phone_data_t2 < we:
                cs = 1
            elif phone_data_t2 == we:
                cs = 4
            elif phone_data_t2 > we:
                cs = 4
            else:
                print('UNHANDLED CASE')
                
        elif phone_data_t1 == ws:
            if ws < phone_data_t2 < we:
                cs = 1
            elif phone_data_t2 == we:
                cs = 4
            elif phone_data_t2 > we:
                cs = 4
            else:
                print('UNHANDLED CASE')
                
        elif ws < phone_data_t1 < we:
            if ws < phone_data_t2 < we:
                cs = 2
            elif phone_data_t2 == we:
                cs = 3
            elif phone_data_t2 > we:
                cs = 3
            else:
                print('UNHANDLED CASE')
        else:
            pass
        return cs
    @staticmethod
    def classify_sensor_state(ws, we, sens_start, sens_end):

        # - str: Classification of the sensor state:
        #         - 'inner case 2' if sens_start >= ws and sens_end <= we
        #         - 'already active (case 4)' if sens_start < ws and sens_end <= we
        #         - 'persistent (case 3)' if sens_start >= ws and sens_end > we
        #         - 'already active and persistent state (case 1)' if sens_start < ws and sens_end > we
        #         - 'invalid' if the input values do not satisfy any condition
        
        if sens_start >= ws and sens_end <= we:
            return 2#'inner case 2'
        elif sens_start < ws and sens_end <= we:
            return 1#'already active (case 1)'
        elif sens_start >= ws and sens_end > we:
            return 3#'persistent (case 3)'
        elif sens_start < ws and sens_end > we:
            return 4#'already active and persistent state (case 4)'
        else:
            return -99#'invalid'
    @staticmethod
    def convert_milliseconds_to_datetime(milliseconds):
        # Convert milliseconds to seconds
        # milliseconds = 1542204466209
        seconds = milliseconds / 1000
        # Convert seconds to a datetime object
        dt_object = datetime.utcfromtimestamp(seconds)
        italy_timezone = pytz.timezone('Europe/Rome')
        italy_time = dt_object.replace(tzinfo=pytz.utc).astimezone(italy_timezone)
        # Format the datetime object as a string (HH:MM:SS)
        formatted_time = italy_time.strftime('%H:%M:%S')
        # formatted_time = dt_object.strftime("%H:%M:%S")

        return formatted_time
    
    @staticmethod
    def convert_hhmmss_to_ampm(hhmmss_time):

        # Convert hh:mm:ss string to datetime object
        dt_obj = datetime.strptime(hhmmss_time, "%H:%M:%S")

        # Format as hh:mm:ss AM/PM
        # formatted_time = dt_obj.strftime("%I:%M:%S%P")
        formatted_time = dt_obj.strftime("%-I:%M %P") ### ubuntu
        # formatted_time = dt_obj.strftime("%#I:%M %p") ### Windows


        return formatted_time
    
    @staticmethod
    def combine_sentences_part_1_new(sentences, all_1_or_4, first_call_flag):
        if len(sentences) == 0:
            combined_sentence = ""
        elif len(sentences) == 1:
            combined_sentence = sentences[0]
        elif len(sentences) == 2:
            if all_1_or_4:
                combined_sentence = ', and '.join(sentences)
            else:
                combined_sentence = ', then '.join(sentences)
        else:
            if all_1_or_4:
                combined_sentence = ', '.join(sentences[:-1]) + ', and ' + sentences[-1]
            else:
                combined_sentence = ', then '.join(sentences[:-1]) + ', and then ' + sentences[-1]
        

        if first_call_flag == True:
            combined_sentence = "Here, " + combined_sentence + "."
        else:
            combined_sentence = "Then, " + combined_sentence + "."

        return combined_sentence
    
    @staticmethod    
    def combine_sentences_part_2(sentences):
        return " ".join(sentences)
      
    # device_name, case_value =  sensorDevice, caseValue 
    # t1_t2 = (turn_on_time, turn_off_time)
    # @staticmethod
    def generate_magnetic_sensor_sentence(self, sensor_id, case_value, t1_t2):

        # print(self.config_loader.get_sensor_info(sensor_id))
        # print(case_value)
        # print('.........................')
        # case_value_mapping = {2: 'inner_state', 3: 'persistent_state', 1: 'already_active_state', 4: 'already_active_and_persistent_state'}
        # state = case_value_mapping[case_value]
        # helping_verb = self.config_loader.get_sensor_info(sensor_id)[state]['helping_verb']
        # verb = self.config_loader.get_sensor_info(sensor_id)[state]['verb']
        # preposition = self.config_loader.get_sensor_info(sensor_id)[state]['preposition']
        # household_item_monitored = self.config_loader.get_sensor_info(sensor_id)['household_item_monitored'].lower()
        # print(helping_verb, verb, preposition,household_item_monitored)        

        case_value_mapping = {2: 'inner_state', 3: 'persistent_state', 1: 'already_active_state', 4: 'already_active_and_persistent_state'}
        state = case_value_mapping[case_value]

        sensorProperty = self.config_loader.sensor_details[sensor_id]['sensor_property']
        sensor_property_wise_states = self.config_loader.config_sensor_properties[sensorProperty]

        helping_verb = sensor_property_wise_states[case_value_mapping[case_value]]['helping_verb']
        verb =sensor_property_wise_states[case_value_mapping[case_value]]['verb']
        preposition = sensor_property_wise_states[case_value_mapping[case_value]]['preposition']
        household_item_monitored = self.config_loader.config['sensors'][sensor_id]['household_item_monitored']

        print(helping_verb, verb, preposition,household_item_monitored,'XXXXXXXXXXXx')

        t1_dash, t2_dash = t1_t2[0], t1_t2[1] 
        time_difference_seconds = int(np.ceil(np.abs(t2_dash - t1_dash) / 1000))

        if time_difference_seconds == 1:
            time_unit = "second"
        else:
            time_unit = "seconds" 

        part_1 = ''
        part_2 = ''
        # device_name = sensor_device_dict[activated_sensor_name]
        ## case 2 inner case 3 persistent case 1 and case 4 are already active
        if case_value == 2:
            part_1 = f'they {helping_verb} {verb} the {household_item_monitored}. After {time_difference_seconds} {time_unit}, they close the {household_item_monitored}'
            part_2 = ''
        elif case_value == 3:
            part_1 = f'they {helping_verb} {verb} the {household_item_monitored}'
            part_2 = ''
        elif case_value == 1:
            part_1 = f"the {household_item_monitored} is already open"
            part_2 = f"After {time_difference_seconds} {time_unit}, they close the {household_item_monitored}."
        elif case_value == 4:
            part_1 = f"the {household_item_monitored} is already open"
            part_2 = ''
        else:
            part_1 = ''
            part_2 = ''
        print(part_1, part_2,case_value)
        return part_1, part_2, case_value

    # @staticmethod
    def generate_electric_sensor_sentence(self, sensor_id, case_value, t1_t2):
        # case_value_mapping = {2: 'inner_state', 3: 'persistent_state', 1: 'already_active_state', 4: 'already_active_and_persistent_state'}
        # state = case_value_mapping[case_value]
        # helping_verb = self.config_loader.get_sensor_info(sensor_id)[state]['helping_verb']
        # verb = self.config_loader.get_sensor_info(sensor_id)[state]['verb']
        # preposition = self.config_loader.get_sensor_info(sensor_id)[state]['preposition']
        # household_item_monitored = self.config_loader.get_sensor_info(sensor_id)['household_item_monitored'].lower()
        # print(helping_verb, verb, preposition,household_item_monitored)

        case_value_mapping = {2: 'inner_state', 3: 'persistent_state', 1: 'already_active_state', 4: 'already_active_and_persistent_state'}
        state = case_value_mapping[case_value]

        sensorProperty = self.config_loader.sensor_details[sensor_id]['sensor_property']
        sensor_property_wise_states = self.config_loader.config_sensor_properties[sensorProperty]

        helping_verb = sensor_property_wise_states[case_value_mapping[case_value]]['helping_verb']
        verb =sensor_property_wise_states[case_value_mapping[case_value]]['verb']
        preposition = sensor_property_wise_states[case_value_mapping[case_value]]['preposition']
        household_item_monitored = self.config_loader.config['sensors'][sensor_id]['household_item_monitored']

        print(helping_verb, verb, preposition,household_item_monitored,'XXXXXXXXXXXx')

        t1_dash, t2_dash = t1_t2[0], t1_t2[1] 
        time_difference_seconds = int(np.ceil(np.abs(t2_dash - t1_dash) / 1000))
        
        if time_difference_seconds == 1:
            time_unit = "second"
        else:
            time_unit = "seconds" 

        part_1 = ''
        part_2 = ''
        # device_name = sensor_device_dict[activated_sensor_name]

        if case_value == 2:
            part_1 = f'they {helping_verb} {verb} the {household_item_monitored}. After {time_difference_seconds} {time_unit}, they turn off the {household_item_monitored}'
            part_2 = ''
        elif case_value == 3:
            part_1 = f'they {helping_verb} {verb} the {household_item_monitored}'
            part_2 = ''
        elif case_value == 1:
            part_1 = f"the {household_item_monitored} {helping_verb} already {verb}"
            part_2 = f"After {time_difference_seconds} {time_unit}, they turn off the {household_item_monitored}."
        elif case_value == 4:
            part_1 = f"the {household_item_monitored} is already {verb}"
            part_2 = ''
        else:
            part_1 = ''
            part_2 = ''

        # if case_value == 2:
        #     part_1 = f'they turn on the {device_name}. After {time_difference_seconds} {time_unit}, they turn off the {device_name}'
        #     part_2 = ''
        # elif case_value == 3:
        #     part_1 = f'they turn on the {device_name}'
        #     part_2 = ''
        # elif case_value == 1:
        #     part_1 = f"the {device_name} is already turned on"
        #     part_2 = f"After {time_difference_seconds} {time_unit}, they turn off the {device_name}."
        # elif case_value == 4:
        #     part_1 = f"the {device_name} is already turned on"
        #     part_2 = ''
        # else:
        #     part_1 = ''
        #     part_2 = ''

        return part_1, part_2, case_value
    

    # @staticmethod
    def generate_pir_sensor_sentence(self, sensor_id, case_value, t1_t2):
        # case_value_mapping = {2: 'inner_state', 3: 'persistent_state', 1: 'already_active_state', 4: 'already_active_and_persistent_state'}
        # state = case_value_mapping[case_value]
        # helping_verb = self.config_loader.get_sensor_info(sensor_id)[state]['helping_verb']
        # verb = self.config_loader.get_sensor_info(sensor_id)[state]['verb']
        # preposition = self.config_loader.get_sensor_info(sensor_id)[state]['preposition']
        # household_item_monitored = self.config_loader.get_sensor_info(sensor_id)['household_item_monitored'].lower()

        case_value_mapping = {2: 'inner_state', 3: 'persistent_state', 1: 'already_active_state', 4: 'already_active_and_persistent_state'}
        state = case_value_mapping[case_value]

        sensorProperty = self.config_loader.sensor_details[sensor_id]['sensor_property']
        sensor_property_wise_states = self.config_loader.config_sensor_properties[sensorProperty]

        helping_verb = sensor_property_wise_states[case_value_mapping[case_value]]['helping_verb']
        verb =sensor_property_wise_states[case_value_mapping[case_value]]['verb']
        preposition = sensor_property_wise_states[case_value_mapping[case_value]]['preposition']
        household_item_monitored = self.config_loader.config['sensors'][sensor_id]['household_item_monitored']

        print(helping_verb, verb, preposition,household_item_monitored,'XXXXXXXXXXXx')
        t1_dash, t2_dash = t1_t2[0], t1_t2[1] 
        time_difference_seconds = int(np.ceil(np.abs(t2_dash - t1_dash) / 1000))
        
        if time_difference_seconds == 1:
            time_unit = "second"
        else:
            time_unit = "seconds" 

        part_1 = ''
        part_2 = ''
        # device_name = sensor_device_dict[activated_sensor_name]

        if case_value == 2:
            part_1 = f'they {helping_verb} {verb} {preposition} the {household_item_monitored}. They stay near the {household_item_monitored} for {time_difference_seconds} {time_unit}'
            part_2 = ''
        elif case_value == 3:
            part_1 = f'they {helping_verb} {verb} {preposition} the {household_item_monitored}'
            part_2 = ''
        elif case_value == 1:
            part_1 = f"they {helping_verb} {verb} already {preposition} the {household_item_monitored}"
            part_2 = f"They stay near the {household_item_monitored} for {time_difference_seconds} {time_unit}."
        elif case_value == 4:
            part_1 = f"they {helping_verb} {verb} already {preposition} the {household_item_monitored}"
            part_2 = ''
        else:
            part_1 = ''
            part_2 = ''

        return part_1, part_2, case_value

    # @staticmethod
    def generate_pressure_sensor_sentence(self, sensor_id, case_value, t1_t2):
        case_value_mapping = {2: 'inner_state', 3: 'persistent_state', 1: 'already_active_state', 4: 'already_active_and_persistent_state'}
        state = case_value_mapping[case_value]

        sensorProperty = self.config_loader.sensor_details[sensor_id]['sensor_property']
        sensor_property_wise_states = self.config_loader.config_sensor_properties[sensorProperty]

        helping_verb = sensor_property_wise_states[case_value_mapping[case_value]]['helping_verb']
        verb =sensor_property_wise_states[case_value_mapping[case_value]]['verb']
        preposition = sensor_property_wise_states[case_value_mapping[case_value]]['preposition']
        household_item_monitored = self.config_loader.config['sensors'][sensor_id]['household_item_monitored']

        print(helping_verb, verb, preposition,household_item_monitored,'XXXXXXXXXXXx')

               

        t1_dash, t2_dash = t1_t2[0], t1_t2[1] 
        time_difference_seconds = int(np.ceil(np.abs(t2_dash - t1_dash) / 1000))
        
        if time_difference_seconds == 1:
            time_unit = "second"
        else:
            time_unit = "seconds" 

        part_1 = ''
        part_2 = ''
        if case_value == 2:
            part_1 = f'they {helping_verb} {verb} {preposition} the {household_item_monitored}. They stay in the {household_item_monitored} for {time_difference_seconds} {time_unit}'
            part_2 = ''
        elif case_value == 3:
            part_1 = f'they {helping_verb} {verb} {preposition} the {household_item_monitored}'
            part_2 = ''
        elif case_value == 1:
            part_1 = f"they {helping_verb} already {verb} {preposition} the {household_item_monitored}"
            part_2 = f"They stay in the {household_item_monitored} for {time_difference_seconds} {time_unit}."
        elif case_value == 4:
            part_1 = f"they {helping_verb} already {verb} {preposition} the {household_item_monitored}"
            part_2 = ''
        else:
            part_1 = ''
            part_2 = ''        

        return part_1, part_2, case_value

    # @staticmethod
    def generate_phone_sensor_sentence(self, sensor_id, case_value, t1_t2, flag):
        case_value_mapping = {2: 'inner_state', 3: 'persistent_state', 4: 'already_active_state', 1: 'already_active_ends_state'}
        state = case_value_mapping[case_value]
        helping_verb = self.config_loader.get_sensor_info(sensor_id)[state]['helping_verb']
        verb = self.config_loader.get_sensor_info(sensor_id)[state]['verb']
        preposition = self.config_loader.get_sensor_info(sensor_id)[state]['preposition']
        household_item_monitored = self.config_loader.get_sensor_info(sensor_id)['household_item_monitored'].lower()

        t1_dash, t2_dash = t1_t2[0], t1_t2[1] 
        time_difference_seconds = int(np.ceil(np.abs(t2_dash - t1_dash) / 1000))
        
        if time_difference_seconds == 1:
            time_unit = "second"
        else:
            time_unit = "seconds" 

        part_1 = ''
        part_2 = ''        
        if case_value == 1:
            if flag == 0:
                part_1 = f"they {helping_verb} already {verb} in a {household_item_monitored} they started before"
                part_2 = f"After {time_difference_seconds} {time_unit}, they end the {household_item_monitored}."
            else:
                part_1 = f"the {household_item_monitored} continues" 
                part_2 = f"After {time_difference_seconds} {time_unit}, they end the {household_item_monitored}."
            
        elif case_value == 2:
            part_1 =  f"they {helping_verb} {verb} a {household_item_monitored}. After {time_difference_seconds} {time_unit}, they end the {household_item_monitored}"
            part_2 = ''
        elif case_value == 3:
            part_1 = f"they {helping_verb} {verb} a {household_item_monitored}"
            part_2 = ''
        elif case_value == 4:
            if flag == 0:
                part_1 = f"they {helping_verb} already {verb} in a {household_item_monitored} they started before"
                part_2 = ''
                flag = 99
            else:
                part_1 = f"the {household_item_monitored} continues" 
                part_2 = ''
        else:
            part_1 = ''
            part_2 = '' 
        return part_1, part_2, case_value, flag

    #activated_sensor_case_value= activated_sensor_list
    # @staticmethod 
    def generate_sensor_sentence_GITHUB(self,activated_sensor_case_value, location_name, flag, ls_le, first_call_flag, stoveFlag):
        ## [{'kitchen': [['R2', 3]]}, {'dining_room': []}, {'kitchen': [['R1', 4]]}]
        ## [['E1', 4], ['R5', 3], ['R7', 3]]
        sensor_sentence = ''
        temp_flag = flag
        if len(activated_sensor_case_value) > 0:
            temporal_word_sensor = ''
            punctuation_list = [','] * len(activated_sensor_case_value)
            punctuation_list[-1] = '.'
            case_value = -99
            part_1_sentences, part_2_sentences = [],[]
            for i in range(len(activated_sensor_case_value)):
                
                # print(activated_sensor_case_value, ls_le)
                if activated_sensor_case_value[i][1] == 1:
                    turn_on_time, turn_off_time = ls_le[0], activated_sensor_case_value[i][3]
                else:
                    turn_on_time, turn_off_time = activated_sensor_case_value[i][2], activated_sensor_case_value[i][3]


                sensorDevice = self.config_loader.sensor_details[activated_sensor_case_value[i][0]]['household_item_monitored']
                sensorRoom = self.config_loader.sensor_details[activated_sensor_case_value[i][0]]['room']
                sensorType = self.config_loader.sensor_details[activated_sensor_case_value[i][0]]['sensor_type']
                caseValue = activated_sensor_case_value[i][1]
                # print(sensorDevice, sensorRoom, sensorType, sensorProperty, caseValue,sensor_property_wise_states, '<<<<<----')
                
                

                if 'magnetic' in sensorType.lower():
                    part_1, part_2, case_value  = self.generate_magnetic_sensor_sentence(activated_sensor_case_value[i][0], caseValue, (turn_on_time, turn_off_time)) 
                
                elif 'pressure' in sensorType.lower():
                    part_1, part_2, case_value  = self.generate_pressure_sensor_sentence(activated_sensor_case_value[i][0], caseValue, (turn_on_time, turn_off_time)) 

                elif 'electric' in sensorType.lower():
                    part_1, part_2, case_value  = self.generate_electric_sensor_sentence(activated_sensor_case_value[i][0], caseValue, (turn_on_time, turn_off_time)) 

                elif 'smartphone' in sensorType.lower():
                    part_1, part_2, case_value, temp_flag = self.generate_phone_sensor_sentence(activated_sensor_case_value[i][0], caseValue, (turn_on_time, turn_off_time), flag) 

                part_1_sentences.append((part_1, case_value))
                part_2_sentences.append(part_2)
                
            ## [1, 4] indicates that already active
            all_1_or_4 = all(case_value in [1, 4] for _, case_value in part_1_sentences)           
            result_part_1_sentences = Window2Text.combine_sentences_part_1_new([sentence for sentence, _ in part_1_sentences], all_1_or_4, first_call_flag) 
            result_part_2_sentences = Window2Text.combine_sentences_part_2(part_2_sentences)
            sensor_sentence = result_part_1_sentences + (" " + result_part_2_sentences if result_part_2_sentences else "")
            
        return sensor_sentence, temp_flag

    @staticmethod
    def generate_location_sentence_new_GITHUB(vl, location_name,count_location_visited):
        ## [{'kitchen': [['R2', 3]]}, {'dining_room': []}, {'kitchen': [['R1', 4]]}]
        ## [['E1', 4], ['R5', 3], ['R7', 3]]

        location_sentence = ''
        emporal_word_location = ''
        location_name = location_name.lower().replace('_',' ')
        if count_location_visited == 1:
            if location_name.lower().replace('_',' ') == 'out':
                location_sentence = f"The subject is outside the home. " # Introduce one space after the sentence
            else:              
                location_sentence = f"The subject is in the {location_name.lower().replace('_',' ')}. " # Introduce one space after the sentence
 
                
        elif count_location_visited > 1:
            if vl == 0:
                temporal_word_sensor = 'First,'
                if location_name == 'out':
                    location_sentence = f"{temporal_word_sensor} the subject is outside the home. "
                else:
                    location_sentence = f"{temporal_word_sensor} the subject is in the {location_name}. "
            else:
                temporal_word_sensor = 'Then,'
                if location_name == 'out':
                    location_sentence = f"{temporal_word_sensor} they go outside the home. "
                else:
                    location_sentence = f"{temporal_word_sensor} they go to the {location_name}. "
                    
        else: 
            location_sentence = 'XXXXXXXXXXXXXXXXXXXXXXXXXx'


        return location_sentence
    @staticmethod
    def process_window_label(temp_label_data):
        if len(temp_label_data) > 0:
            # Lists to store activity names and durations
            activity_names = []
            activity_durations = []

            # Iterate through each data point
            for data_point in temp_label_data:
                activity_name = data_point['Label']
                activity_name = activity_name.lower().replace('_', ' ')
                activity_names.append(activity_name)
                
                # Calculate activity duration
                activity_duration = data_point['t2'] - data_point['t1']
                activity_durations.append(activity_duration)
            
            # Find activity with max duration
            max_duration_index = activity_durations.index(max(activity_durations))
            activity_name_with_max_duration = activity_names[max_duration_index]
            
            # Find sixteen_seconds_window_start and sixteen_seconds_window_end
            sixteen_seconds_window_start = temp_label_data[0]['window start']
            sixteen_seconds_window_end = temp_label_data[-1]['window end']
            
            # Check if 'TRANSITION' label exists
            transition_exists = any(data_point == 'transition' for data_point in activity_names)
            
            # Prepare output based on TRANSITION label
            if transition_exists:
                # In activity transition
                result = [activity_names, "transition", ("transition", sixteen_seconds_window_start, sixteen_seconds_window_end)]
            else:
                # Not in activity transition
                result = [activity_names, activity_name_with_max_duration, (activity_name_with_max_duration, sixteen_seconds_window_start, sixteen_seconds_window_end)]
            
            return result[0], result[1], result[2]
        else:
            return [],'none', ('none',-99,-99)

    def get_sensor_ids_by_location(self, room):
        config_path_sensors = self.config_path
        with open(config_path_sensors, 'r') as file:
            sensors_data = yaml.safe_load(file)

        sensor_ids = []
        for sensor_id, sensor_info in sensors_data['sensors'].items():
            if sensor_info['room'].lower() == room.lower():
                sensor_ids.append(sensor_id)
        sens_ids = [s for s in sensor_ids if 'common' not in s]
        return sens_ids  

    # @staticmethod
    def generate_user_questions_version_GITHUB(self,w_t):
        """
        This function is called for each window
        """
        # user_question, user_label, user_all_valid_label, user_final_label = [], [], [], []
        
        # uqst = ''
        # generated_location_sensor_sentence = ''
        # phone_text_2 = ''
        # past_window_txt = '' 
        
        # lab_modified = []
        
        #final_user_text, lab_modified, vls, al, al_window
        loc_env_phone_label = w_t
        loc_data = loc_env_phone_label[0] # location visited
        sens_data = loc_env_phone_label[1] # sensor activated
        respective_window = loc_env_phone_label[2] ## window start and window end
        a,b = respective_window[0],respective_window[1]
        label_data = loc_env_phone_label[3] # original label
        # phone_data = loc_env_phone_label[3] # smartphone used or not

        vls, al, al_window = Window2Text.process_window_label(label_data) # all_labels_in_a_window, true_label, true_label_window
        
        # count = 0
        # count_var = 0
        # # Check if atleast one location is visited
        # location_activated_sensor_pair = []
        # location_activated_phone_pair = []
        uq = ''
        if len(loc_data) > 0:
            # sort the location data according to start time of that location visit in a particular window
            loc_data = sorted(loc_data, key=lambda x: x['t1'])
            # Extract the location visited by the human target in the house
            # locations_visited = [entry['Location'] for entry in loc_data]
            #Loop over the each location visited
            flag = 0
            
            for l in range(len(loc_data)):
                # print(l)
                # global isExecuted, stoveFlag
                # isExecuted = False
                # stoveFlag = True
                first_call_flag = True
                # print('Value of L=',l)
                temp = loc_data[l] # Extract all the information of the first location
                temp_location = temp['Location'] # nameof the location
                ws = temp['t1'] # Location visit start time in a window of 16 seconds
                we = temp['t2'] # Location visit end time in a window of 16 seconds
                
                # print(temp_location, '\t', ws, '\t', we, '\t', a, '\t', b)   
                formatted_result_1 = Window2Text.convert_hhmmss_to_ampm(Window2Text.convert_milliseconds_to_datetime(a))
                location_sentence = Window2Text.generate_location_sentence_new_GITHUB(l, temp_location.lower(),len(loc_data))

                # Now pick which sensors were active at the first location
                # check if atleast one sensor is activated
                sensor_sentence = ''
                activated_sensor_list = []
                if len(sens_data) > 0:
                    # sort the data according to the start time
                    sorted_sens_data = sorted(sens_data, key=lambda x: x['t1'])
                    # which sensors are present at the location
                    # sensor_present = self.config_loader.get_sensors_present_at_a_location(temp_location.lower())

                  
                    sensor_present = self.get_sensor_ids_by_location(temp_location.lower().replace('_',' '))
                    
                    # Extract all the sensors which are activated in the time window
                    # sensor_activated = [entry['Sensor'] for entry in sorted_sens_data]
                    sensor_activated = [entry.get('event_id', entry.get('Sensor')) for entry in sorted_sens_data]   

                    sensors_activated_at_the_location = []
                    for sa in range(len(sensor_present)):
                        if sensor_present[sa] in sensor_activated:
                            sensors_activated_at_the_location.append(sensor_present[sa])

                    for sa in range(len(sensor_activated)):
                        if sensor_activated[sa] in ['S1', 'S2']:
                            sensors_activated_at_the_location.append(sensor_activated[sa])

                    
                    # sensors which are activated at the particular location
                    # sensors_activated_at_the_location = sorted(list(set(sensor_present) & set(sensor_activated)))
                
                    ### ab aisa bhi ho sakta hai ki ek aadmi kai baar ek particular location ko visit kiya ho
                    ### or har baar same sensor activate ho, to muhjhe ye identify karna hai ki uss visited
                    ### location k kon kon se sensors ek particular window me activate hue hain 
                    ### For example, window in consideration is t = 0 to t = 100. Ek aadmi aataa hai and kitchen 
                    ### visit karta hai t = 10 to t = 15 tak and again wo aadmi t=35 se t=50 tak kitchen visit
                    ### karta hai. pahle visit par [R1, R2] activate hue an doosri visit me [R2, R5] to mujhe
                    ### dono visit me jo sensors activate hue hain unko segregate karna hai
                    
                    # info_of_sensors_activated_at_the_location = [item for item in sorted_sens_data if item['Sensor'] in sensors_activated_at_the_location]

                    info_of_sensors_activated_at_the_location = [item for item in sorted_sens_data 
                                                                if item.get('event_id') in sensors_activated_at_the_location or item.get('Sensor') in sensors_activated_at_the_location]
                    
                   
                    
                    for m in range(len(info_of_sensors_activated_at_the_location)):
                        # temp_sens = info_of_sensors_activated_at_the_location[m]['Sensor']
                        temp_sens = info_of_sensors_activated_at_the_location[m].get('Sensor')
                        if temp_sens is None:
                            temp_sens = info_of_sensors_activated_at_the_location[m].get('event_id')
                        temp_sens_start = info_of_sensors_activated_at_the_location[m]['t1']
                        temp_sens_end = info_of_sensors_activated_at_the_location[m]['t2']
                        
                        isTrue = Window2Text.is_overlap((temp_sens_start,temp_sens_end), (ws,we))
                        
                        if isTrue == False: ## If no overlap is location visit time and sensor activation time then do nothing 
                            pass
                        else:
                            window_status = Window2Text.classify_sensor_state(a, b, temp_sens_start, temp_sens_end)
                            # window_status = Window2Text.location_sensor_phone_start_end(ws, we, temp_sens_start, temp_sens_end)
                            sensor_property = self.config_loader.sensor_details[temp_sens]['sensor_property']
                            
                            activated_sensor_list.append([temp_sens, window_status, temp_sens_start, temp_sens_end, sensor_property])  
                    
                ## First get the already active sensor
                filtered_list = [sublist for sublist in activated_sensor_list if sublist[1] == 1 or sublist[1] == 4]
                filtered_list = sorted(filtered_list, key=lambda x: (x[2], x[3])) # sort by startn and end time
                sensor_sentence_filtered_list, returned_flag_1 = self.generate_sensor_sentence_GITHUB(filtered_list, temp_location.lower(),flag, (max(a,ws),b),first_call_flag,'999')
                # sensor_sentence_filtered_list, returned_flag_1 = sensor_sentence, flg
                if sensor_sentence_filtered_list:
                    print('hi')
                    first_call_flag = False
                ## List the sensors which are not active before this window
                print('---->',sensor_sentence_filtered_list)
                remaining_list = [sublist for sublist in activated_sensor_list if sublist not in filtered_list]
                remaining_list = sorted(remaining_list, key=lambda x: (x[2], x[3]))
                sensor_sentence_remaining_list, returned_flag_2 = self.generate_sensor_sentence_GITHUB(remaining_list, temp_location.lower(),flag, (a,b), first_call_flag,'999' )
                print('---->',sensor_sentence_remaining_list)
                
                combined_sentences = ' '.join(filter(None, [sensor_sentence_filtered_list, sensor_sentence_remaining_list]))
                uq =  uq + ' ' +location_sentence + combined_sentences
                
                flag = returned_flag_2 if returned_flag_2 > returned_flag_1 else returned_flag_1

            return uq, vls, al, al_window, formatted_result_1




# class DataLoderUCI:
#     def __init__(self,data_path,config_path, config_loader):
#         self.data_path = data_path
#         self.config_path = config_path
#         self.config_loader = config_loader

#     def filter_data_by_window(self, data_miliseconds, window_start, window_end):
#         filtered_rows = []
#         indx_list = []
#         for i in range(len(data_miliseconds)):
#             row = data_miliseconds[i]
#             start, end, device_name, sensor_name, location_name, sensor_id = row[0], row[1], row[2], row[3], row[4], row[5]
#             # if window_start <= start <= window_end or window_start <= end <= window_end:
#             if window_start <= end and start <= window_end:
#                 filtered_rows.append((start, end, device_name, sensor_name, location_name, sensor_id))
#                 indx_list.append(i)
#         filtered_rows = np.array(filtered_rows, dtype='object') 
#         print(filtered_rows)
#         return filtered_rows, indx_list

#     def filter_label_by_window(self, label_miliseconds, window_start, window_end):
#         filtered_rows = []
#         activity_durations = defaultdict(int)
#         indx_list = []
#         for i in range(len(label_miliseconds)):
#             row = label_miliseconds[i]
#             start, end, activity_name = row[0], row[1], row[2]
#             if window_start <= end and start <= window_end:
#                 indx_list.append(i)
#                 # Calculate the effective duration within the window
#                 effective_start = max(start, window_start)
#                 effective_end = min(end, window_end)
#                 # print(start, end, window_start, window_end, effective_start, effective_end)
#                 duration = effective_end - effective_start
#                 filtered_rows.append((effective_start, effective_end, duration, activity_name))
#                 # Track the cumulative duration of each activity
#                 activity_durations[activity_name] += duration

#         filtered_rows = np.array(filtered_rows, dtype='object')
#         if filtered_rows.shape[0] == 0:
#             activity_names = ['Invalid_Window']
#             max_duration_activity = 'Invalid_Window'
#         else:
#             activity_names = list(filtered_rows[:, 3])
#             max_duration_activity = max(activity_durations, key=activity_durations.get)
        
#         return filtered_rows, activity_names, max_duration_activity, indx_list          

#     def convert_milliseconds_to_datetime_2(milliseconds, format='%Y-%m-%d %H:%M:%S'):
#         # Convert milliseconds to seconds
#         seconds = milliseconds / 1000.0
#         # Create a datetime object from the timestamp in UTC
#         dt = datetime.utcfromtimestamp(seconds)
#         # Return formatted datetime string
#         return dt.strftime(format)             

#     def load_data_or_label(self, dataset_path, filename_subject_a):
#         file_path = os.path.join(dataset_path, filename_subject_a)
#         data_with_normalized_spacing = self.normalize_spacing(file_path)
#         data = self.convert_to_numpy_array(data_with_normalized_spacing)
#         return data
    
#     def normalize_spacing(self, file_path):
#         with open(file_path, 'r') as file:
#             lines = file.readlines()
        
#         normalized_lines = []
#         for line in lines:
#             # Replace multiple spaces with a single space
#             normalized_line = re.sub(r'\s+', ' ', line).strip()
#             normalized_lines.append(normalized_line)
        
#         return normalized_lines

#     def convert_to_numpy_array(self, normalized_lines):
#         activity_list = []
#         # Iterate over each string in the normalized_lines list
#         for line in normalized_lines:
#             # Split the string into words using the space as a delimiter
#             word_list = []
#             words = line.split()
#             # Iterate over each word in the split string
#             for word in words:
#                 # Add the word to the word_list
#                 word_list.append(word)
#             activity_list.append(word_list)
#         activity_list =  np.array(activity_list,dtype='object')   
#         return activity_list    

#     def add_unmatched_to_label(self, data, label):
#         unmatched_indices, unmatched_rows = self.find_unmatched_rows(data, label)
        
#         # Create new rows with "Other" label
#         new_rows = []
#         for row in unmatched_rows:
#             new_row = [row[0], row[1], row[2], row[3], "Other"]
#             new_rows.append(new_row)
        
#         new_rows = np.array(new_rows)
        
#         # Concatenate new rows to the label matrix
#         updated_label = np.concatenate((label, new_rows), axis=0)
        
#         # Create datetime objects for sorting
#         start_datetimes = np.array([datetime.strptime(f'{row[0]} {row[1]}', '%Y-%m-%d %H:%M:%S') for row in updated_label])
        
#         # Get the sorted indices
#         sorted_indices = np.argsort(start_datetimes)
        
#         # Sort the label matrix
#         sorted_label = updated_label[sorted_indices]
        
#         return sorted_label


#     def find_unmatched_rows(self, data, label):
#         # Function to convert date and time to a datetime object
#         def to_datetime(date_str, time_str):
#             return datetime.strptime(date_str + ' ' + time_str, '%Y-%m-%d %H:%M:%S')
        
#         # Convert data start and end times to datetime objects
#         data_start_times = np.array([to_datetime(row[0], row[1]) for row in data])
#         data_end_times = np.array([to_datetime(row[2], row[3]) for row in data])
        
#         # Convert label start and end times to datetime objects
#         label_start_times = np.array([to_datetime(row[0], row[1]) for row in label])
#         label_end_times = np.array([to_datetime(row[2], row[3]) for row in label])
        
#         # Identify rows in data that do not have a corresponding label (no overlap)
#         unmatched_indices = []
#         unmatched_rows = []
        
#         for i in range(len(data_start_times)):
#             data_start = data_start_times[i]
#             data_end = data_end_times[i]
            
#             overlap_found = False
#             for j in range(len(label_start_times)):
#                 label_start = label_start_times[j]
#                 label_end = label_end_times[j]
                
#                 # Check for overlap
#                 if not (data_end < label_start or data_start > label_end):
#                     overlap_found = True
#                     break
            
#             if not overlap_found:
#                 unmatched_indices.append(i)
#                 unmatched_rows.append(data[i])
        
#         # Convert unmatched rows to a numpy array
#         unmatched_rows = np.array(unmatched_rows)
        
#         return unmatched_indices, unmatched_rows



#     def data_with_time_in_miliseconds(self, data):
#         modified_data = np.zeros((len(data),6), dtype='object')
#         for i in range(len(data)):
#             start_date = data[i][0]
#             start_hh_mm_ss = data[i][1]
#             end_date = data[i][2]
#             end_hh_mm_ss = data[i][3]
#             device_name, sensor_name, location_name, sensor_id = data[i][4], data[i][5], data[i][6], data[i][7]
#             date_time_str = str(start_date) + ' ' + str(start_hh_mm_ss)
#             start_time_miliseconds = self.date_time_to_milliseconds(date_time_str)
#             # start_time_miliseconds2 = date_time_to_milliseconds_m2(date_time_str)
            
#             date_time_str = str(end_date) + ' ' + str(end_hh_mm_ss)
#             end_time_miliseconds = self.date_time_to_milliseconds(date_time_str)
#             # end_time_miliseconds2 = date_time_to_milliseconds_m2(date_time_str)
            
#             modified_data[i][0], modified_data[i][1] = start_time_miliseconds, end_time_miliseconds
#             modified_data[i][2], modified_data[i][3], modified_data[i][4], modified_data[i][5] = device_name, sensor_name, location_name , sensor_id
#         return modified_data


#     def labels_with_time_in_miliseconds(self, label):
#         modified_label = np.zeros((len(label),3), dtype='object')
#         for i in range(len(label)):
#             start_date = label[i][0]
#             start_hh_mm_ss = label[i][1]
#             end_date = label[i][2]
#             end_hh_mm_ss = label[i][3]
#             activity_name = label[i][4]
#             date_time_str = str(start_date) + ' ' + str(start_hh_mm_ss)
#             start_time_miliseconds = self.date_time_to_milliseconds(date_time_str)
#             # start_time_miliseconds2 = date_time_to_milliseconds_m2(date_time_str)
            
#             date_time_str = str(end_date) + ' ' + str(end_hh_mm_ss)
#             end_time_miliseconds = self.date_time_to_milliseconds(date_time_str)
#             # end_time_miliseconds2 = date_time_to_milliseconds_m2(date_time_str)
            
#             modified_label[i][0], modified_label[i][1] = start_time_miliseconds, end_time_miliseconds
#             modified_label[i][2] = activity_name
#         return modified_label

#     def date_time_to_milliseconds(self, date_time_str):
#         # Convert the string to a datetime object
#         dt_obj = datetime.strptime(date_time_str, "%Y-%m-%d %H:%M:%S")
#         # Get the total seconds from the epoch to the given datetime
#         total_seconds = (dt_obj - datetime(1970, 1, 1)).total_seconds()
#         # Convert seconds to milliseconds
#         milliseconds = int(total_seconds * 1000)
#         return milliseconds


#     def process_filtered_rows(self, filtered_rows):
#         result = []
#         for rw in range(len(filtered_rows)):
#             row = filtered_rows[rw]
#             t1 = row[0]
#             t2 = row[1]
#             sensor_device = row[2]
#             sensor_type = row[3]
#             sensor_room = row[4]
#             sensor_id = row[5]

#             row_dict = {
#                 'Sensor': sensor_id,
#                 't1': t1,
#                 't2': t2,
#                 'sensor_type': sensor_type,
#                 'sensor_device': sensor_device,
#                 'sensor_room': sensor_room
#             }

#             result.append(row_dict)
        
#         return result        