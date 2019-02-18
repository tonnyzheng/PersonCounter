# from imutils.video import VideoStream
import argparse
import imutils
import cv2 # 3.4.5
from utils.dataset import MOT16
from utils.pc_utils import pc_PerImageEvaluation

import time, os, math
import pandas as pd
import logging
from logging.config import fileConfig
fileConfig('logging_config.ini')
logger = logging.getLogger()

class TrackerPersonCounter:
    """
    Detect and track approach for person counter using OpenCV object tracking algorithms.
    Tracker is initialized with bounding box from detection (or ground truth) and following frames are tracked.
    The tracker is reinitialized at a frame rate of of <detectfr>
    """
    def __init__(self, ds, tkr, dt, ws):
        logger.info("Running tracker based person counter")
        self.ds = ds
        self.tracker_algo = tkr
        # frames skipped while detection = detection speed * video frame rate
        self.detect_lag = math.floor(dt * ds.frame_rate)
        self.window_size = ws
        filename =  ds.video_name + "_" + self.tracker_algo + "_pfr" + str(dt) + "_ws" + str(self.window_size) + '.csv'
        logger.info("\nFilename {}\n".format(filename))
        self.path_to_output_file = os.path.join("output", "localtrack", filename)

    def str(self):
        txt = "Tracker person counter \n"
        txt += self.path_to_video + "\n"
        txt += self.tracker_algo + "\n"
        return txt

    def setup(self):
        """ Initialized video stream and detection source"""
        #TODO pick between video and directory
        self.video_stream = cv2.VideoCapture(self.ds.getVideoStream()) #TODO resize
        # self.video_stream = cv2.VideoCapture(self.path_to_video) # open video
        self.gt_df = self.ds.parseAnnotation_OpenCV() #  GT BB in OpenCV tracker format as Pandas DataFrame
        self.result = [] # Result per BB

    def detectOnFrame(self, frame, frame_id):
        """ Perform detection and initialize trackers based on detected objects """
        # Run detection, and filter out based on category and confidence
        logger.info("Frame id {}".format(frame_id))
        bbs = self.gt_df.loc[self.gt_df.frame_id == frame_id][['xmin', 'ymin', 'width', 'height']].values
        #TODO correlate with previous value

        OPENCV_OBJECT_TRACKERS = {
            "csrt": cv2.TrackerCSRT_create,
            "kcf": cv2.TrackerKCF_create,
            "boosting": cv2.TrackerBoosting_create,
            "mil": cv2.TrackerMIL_create,
            "tld": cv2.TrackerTLD_create,
            "medianflow": cv2.TrackerMedianFlow_create,
            "mosse": cv2.TrackerMOSSE_create
        }
        # KCF: Fast and accurate
        # CSRT: More accurate than KCF but slower
        # MOSSE: Extremely fast but not as accurate as either KCF or CSRT

        self.trackers = cv2.MultiTracker_create() # Multi object tracker
        # create a new object tracker for each object and add it to our multi-object tracker
        for bb in bbs:
            box = tuple(bb)
            object_tracker = OPENCV_OBJECT_TRACKERS[self.tracker_algo]()
            self.trackers.add(object_tracker, frame, box)
        self.log_output(bbs, frame_id, "detect", self.detect_lag)
        #self.showInference(frame, bbs, frame_id, "detect")

    def trackOnFrame(self, frame, frame_id):
        """ Perform update on frame """
        start = time.time()
        (success, bbs) = self.trackers.update(frame) # update tracker
        # frames skipped while tracking = tracking speed * video frame rate
        self.track_lag = math.floor( (time.time() - start) * self.ds.frame_rate )
        self.log_output(bbs, frame_id, "track", self.track_lag)
        #self.showInference(frame, bbs, frame_id, "track")

    def log_output(self, bbs, frame_id, phase, lag):
        """ Log the output for each frame, either detect or track """
        local_id = 1
        for box in bbs:
            (x, y, w, h) = [int(v) for v in box]
            row = [frame_id, phase, local_id, x, y, w, h, lag]
            local_id += 1
            self.result.append(row)
        pass

    def showInference(self, frame, boxes, frame_id, phase):
        """ Display the image and BB for debugging  """
        for box in boxes:
            (x, y, w, h) = [int(v) for v in box]
            cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)

        cv2.imshow("Frame {} {}".format(phase, frame_id), frame)
        key = cv2.waitKey(2000)
        # if key == 27: # Esc key
        #     break
        cv2.destroyAllWindows()

    def run(self):
        """ Detect on leader frame, skipping frames received during the detection; Track subsequent k (window size) frames, skipping frames received during the tracking """
        frame_id = 1 # Received frame
        next_frame_id = 1 # Next frame to process
        k = self.window_size

        while True:
            #logger.info("Frame cnt {} Capture cnt {}".format(frame_id, self.video_stream.get(1))) #cv2.CV_CAP_PROP_POS_FRAMES
            frame = self.video_stream.read()[1]
            if frame is None: # End of video
                break
            # Skip frames received during processing
            if frame_id != next_frame_id:
                frame_id += 1
                continue
            # Detect OR track
            if k == self.window_size: # Window completed
                self.detectOnFrame(frame, frame_id)
                next_frame_id += self.detect_lag
                k = 0
                logger.info("Frame {} DETECT. Skipping {} frame(s) to {}".format(frame_id, self.detect_lag, next_frame_id) )
            else: # Track
                self.trackOnFrame(frame, frame_id)
                next_frame_id += self.track_lag
                k += 1
                logger.info("Frame {} TRACK {}. Skipping {} frame(s) to {}".format(frame_id, k, self.track_lag, next_frame_id) )
            frame_id += 1

        logger.info("Save log to {}".format(self.path_to_output_file))
        res = pd.DataFrame(self.result)
        res.to_csv(self.path_to_output_file, header=False) # contains index

if __name__ == '__main__' :
    # python tracker_person_counter.py -v MOT16-10 -dh ~/4Sem/MTP1/MOT16
    # 2>&1 | tee output/log.txt # Stream log to file
    parser = argparse.ArgumentParser()
    parser.add_argument("-dh", "--dataset_home", type=str, required=True, help="path to dataset home")
    parser.add_argument("-v", "--video", type=str, required=True, help="video stream. e.g: MOT16-10")
    parser.add_argument("-t", "--tracker", type=str, default="csrt",	help="OpenCV object tracker type. Pick from kcf, csrt, mosse, boosting, mil, tld, medianflow ")
    parser.add_argument("-dt", "--detect_speed", type=float, default="0.7",	help="detection speed (sec)")
    parser.add_argument("-w", "--window_size", type=int, default="35",	help="Window size (#frames) of tracking")

    args = parser.parse_args()
    for key, value in sorted(vars(args).items()):
        logger.info(str(key) + ': ' + str(value))

    # Dataset
    dataset_name, vid = args.video.split('-')
    if dataset_name == "MOT16":
        ds = MOT16(args.dataset_home, int(vid))
    else:
        logger.info("Invalid dataset")
        exit()
    tpc = TrackerPersonCounter(ds, args.tracker, args.detect_speed, args.window_size)
    tpc.setup()
    tpc.run()
    
    # for tracker in ["kcf", "csrt", "mosse", "boosting", "mil", "tld", "medianflow"]:
    #     for detect_speed in [0, 0.1, 0.3, 0.5, 0.7, 1.0, 1.5, 1.7, 2]:
    #         for window_size in range(0,41,5):
    #             try:
    #                 tpc = TrackerPersonCounter(ds, tracker, detect_speed, window_size)
    #                 tpc.setup()
    #                 tpc.run()
    #             except Exception as ex:
    #                 logger.error(ex)
    #                 logger.error("Fail {}".format(tpc.path_to_output_file))
    logger.info("Done")
