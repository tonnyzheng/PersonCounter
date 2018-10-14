import argparse
import basic_person_counter

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--model',type=int,nargs='?', default=2)
    parser.add_argument('--video',type=int, nargs='?', default=10)
    parser.add_argument('--useGT',type=bool, nargs='?', default=True)
    parser.add_argument('--iou',type=float, nargs='?', default=0.5)

    args = parser.parse_args()
    bpc = basic_person_counter.BasicPersonCounter(args.useGT, args.video, args.model, args.iou)
    print bpc.str()
    #bpc.assign_id()
    bpc.visualize_groundtruth()
    print "Done"

if __name__ == "__main__":
    main()