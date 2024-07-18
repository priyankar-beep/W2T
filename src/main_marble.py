# main.py
from utility import ConfigLoader, DataLoader, Window2Text
import os

def main():
    config_path_sensors = '/home/hubble/work/project_generalization/src/marble_sensors.yml'
    config_path_sensors_properties = '/home/hubble/work/project_generalization/src/marble_property.yml'
    config_path_loader = ConfigLoader(config_path_sensors, config_path_sensors_properties)
    config = config_path_loader.config

    data_path = config['dataset']['path'] ## Dataset path
    activity_patterns = sorted(os.listdir(data_path)) ## Scenarios
    data_loader = DataLoader(data_path,activity_patterns,config_path_sensors,config_path_loader)
    result_subjects = data_loader.extract_subject_names()
    subject_data, unified_data = data_loader.subjectwise_windows(result_subjects)

    w2t = Window2Text(config_path_sensors, config_path_loader, config_path_sensors_properties)
    # w_t = subject_data['subject-200']['A1a'][0][178]
    w_t = subject_data['subject-212']['B1e'][0][140]
    aaa = w2t.generate_user_questions_version_GITHUB(w_t)
    print(aaa[0],'<<<+++>>>')
    
if __name__ == "__main__":
    main()

