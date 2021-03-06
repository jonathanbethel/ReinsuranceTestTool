#!/usr/bin/env python
"""
Test tool for reinsurance functaionality and OED data input.
Takes input data in OED format, and invokes the Oasis Platform financial module.
"""
from tabulate import tabulate
import pandas as pd
import shutil
import os
import argparse
import time
import logging
from reinsurance_layer import ReinsuranceLayer, validate_reinsurance_structures
from direct_layer import DirectLayer
import common
from collections import OrderedDict


def load_oed_dfs(oed_dir, show_all=False):
    """
    Load OED data files.
    """

    do_reinsurance = True
    if oed_dir is not None:
        if not os.path.exists(oed_dir):
            print("Path does not exist: {}".format(oed_dir))
            exit(1)
        # Account file
        oed_account_file = os.path.join(oed_dir, "account.csv")
        if not os.path.exists(oed_account_file):
            print("Path does not exist: {}".format(oed_account_file))
            exit(1)
        account_df = pd.read_csv(oed_account_file)

        # Location file
        oed_location_file = os.path.join(oed_dir, "location.csv")
        if not os.path.exists(oed_location_file):
            print("Path does not exist: {}".format(oed_location_file))
            exit(1)
        location_df = pd.read_csv(oed_location_file)

        # RI files
        oed_ri_info_file = os.path.join(oed_dir, "ri_info.csv")
        oed_ri_scope_file = os.path.join(oed_dir, "ri_scope.csv")
        oed_ri_info_file_exists = os.path.exists(oed_ri_info_file)
        oed_ri_scope_file_exists = os.path.exists(oed_ri_scope_file)

        if not oed_ri_info_file_exists and not oed_ri_scope_file_exists:
            ri_info_df = None
            ri_scope_df = None
            do_reinsurance = False
        elif oed_ri_info_file_exists and oed_ri_scope_file_exists:
            ri_info_df = pd.read_csv(oed_ri_info_file)
            ri_scope_df = pd.read_csv(oed_ri_scope_file)
        else:
            print("Both reinsurance files must exist: {} {}".format(
                oed_ri_info_file, oed_ri_scope_file))
        if not show_all:
            account_df = account_df[common.OED_ACCOUNT_FIELDS].copy()
            location_df = location_df[common.OED_LOCATION_FIELDS].copy()
            if do_reinsurance:
                ri_info_df = ri_info_df[common.OED_REINS_INFO_FIELDS].copy()
                ri_scope_df = ri_scope_df[common.OED_REINS_SCOPE_FIELDS].copy()
                ri_info_df['PlacementPercent'] = ri_info_df['PlacementPercent'].astype(float)
    return (account_df, location_df, ri_info_df, ri_scope_df, do_reinsurance)


def run_inuring_level_risk_level(
        inuring_priority,
        account_df,
        location_df,
        items,
        coverages,
        fm_xrefs,
        xref_descriptions,
        ri_info_df,
        ri_scope_df,
        previous_inuring_priority,
        previous_risk_level,
        risk_level):

    reins_numbers_1 = ri_info_df[
        ri_info_df['InuringPriority'] == inuring_priority].ReinsNumber
    if reins_numbers_1.empty:
        return None
    reins_numbers_2 = ri_scope_df[
        ri_scope_df.isin({"ReinsNumber": reins_numbers_1.tolist()}).ReinsNumber &
        (ri_scope_df.RiskLevel == risk_level)].ReinsNumber
    if reins_numbers_2.empty:
        return None

    ri_info_inuring_priority_df = ri_info_df[ri_info_df.isin(
        {"ReinsNumber": reins_numbers_2.tolist()}).ReinsNumber]
    output_name = "ri_{}_{}".format(inuring_priority, risk_level)
    reinsurance_layer = ReinsuranceLayer(
        name=output_name,
        ri_info=ri_info_inuring_priority_df,
        ri_scope=ri_scope_df,
        accounts=account_df,
        locations=location_df,
        items=items,
        coverages=coverages,
        fm_xrefs=fm_xrefs,
        xref_descriptions=xref_descriptions,
        risk_level=risk_level
    )

    reinsurance_layer.generate_oasis_structures()
    reinsurance_layer.write_oasis_files()

    input_name = ""
    if previous_inuring_priority is None and previous_risk_level is None:
        input_name = "ils"
    else:
        input_name = "ri_{}_{}".format(previous_inuring_priority, previous_risk_level)

    reinsurance_layer_losses_df = common.run_fm(
        input_name, output_name, reinsurance_layer.xref_descriptions)

    return reinsurance_layer_losses_df


def run_test(
        run_name,
        account_df, location_df, ri_info_df, ri_scope_df,
        loss_factor,
        do_reinsurance,
        logger=None):
    """
    Run the direct and reinsurance layers through the Oasis FM.abs
    Returns an array of net loss data frames, the first for the direct layers
    and then one per inuring layer.
    """
    t_start = time.time()


    if os.path.exists(run_name):
        shutil.rmtree(run_name)
    os.mkdir(run_name)

    cwd = os.getcwd()

    if os.path.exists(run_name):
        shutil.rmtree(run_name)
    os.mkdir(run_name)

    net_losses = OrderedDict()

    cwd = os.getcwd()
    try:
        os.chdir(run_name)

        direct_layer = DirectLayer(account_df, location_df)
        direct_layer.generate_oasis_structures()
        direct_layer.write_oasis_files()
        losses_df = direct_layer.apply_fm(
            loss_percentage_of_tiv=loss_factor, net=False)
        net_losses['Direct'] = losses_df
        if do_reinsurance:
            (is_valid, reisurance_layers) = validate_reinsurance_structures(
                account_df, location_df, ri_info_df, ri_scope_df)
            if not is_valid:
                print("Reinsuarnce structure not valid")
                for reinsurance_layer in reisurance_layers:
                    if not reinsurance_layer.is_valid:
                        print("Inuring layer {} invalid:".format(
                            reinsurance_layer.inuring_priority))
                        for validation_message in reinsurance_layer.validation_messages:
                            print("\t{}".format(validation_message))
                        exit(0)

            previous_inuring_priority = None
            previous_risk_level = None
            for inuring_priority in range(1, ri_info_df['InuringPriority'].max() + 1):
                # Filter the reinsNumbers by inuring_priority
                reins_numbers = ri_info_df[ri_info_df['InuringPriority'] == inuring_priority].ReinsNumber.tolist()
                risk_level_set = set(ri_scope_df[ri_scope_df['ReinsNumber'].isin(reins_numbers)].RiskLevel)

                for risk_level in common.REINS_RISK_LEVELS:
                    if risk_level not in risk_level_set:
                        continue
                    reinsurance_layer_losses_df = run_inuring_level_risk_level(
                        inuring_priority,
                        account_df,
                        location_df,
                        direct_layer.items,
                        direct_layer.coverages,
                        direct_layer.fm_xrefs,
                        direct_layer.xref_descriptions,
                        ri_info_df,
                        ri_scope_df,
                        previous_inuring_priority,
                        previous_risk_level,
                        risk_level)
                    previous_inuring_priority = inuring_priority
                    previous_risk_level = risk_level

                    if reinsurance_layer_losses_df is not None:
                        net_losses['Inuring priority:{} - Risk level:{}'.format(
                            inuring_priority, risk_level)] = reinsurance_layer_losses_df

    finally:
        os.chdir(cwd)
        t_end = time.time()
        print("Exec time: {}".format(t_end - t_start))

        if logger:
            print("\n\nItems_to_Locations: mapping")
            print(tabulate(direct_layer.report_item_ids(),
                         headers='keys', tablefmt='psql', floatfmt=".2f")) 
            logger.debug("Items_to_Locations: mapping")
            logger.debug(tabulate(direct_layer.report_item_ids(),
                         headers='keys', tablefmt='psql', floatfmt=".2f")) 
    return net_losses



def setup_logger(log_name):
    log_file = "run_{}.log".format(time.strftime("%Y%m%d-%H%M%S"))
    if log_name:
        log_file = "{}.log".format(log_name)

    log_dir = 'logs'
    

    log_level = logging.DEBUG
    #log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    log_format = '%(message)s\n'

    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    #logging.basicConfig(stream=sys.stdout, level=log_level, format=log_format)
    logging.basicConfig(level=log_level,
                        format=log_format,
                        filename=os.path.join(log_dir, log_file),
                        filemode='w')
    return logging.getLogger()



if __name__ == "__main__":
    # execute only if run as a script
    parser = argparse.ArgumentParser(
        description='Run Oasis FM examples with reinsurance.')
    parser.add_argument(
        '-n', '--name', metavar='N', type=str, required=True,
        help='The analysis name. All intermediate files will be "+ \
        policies=a         "saved in a labelled directory.')
    parser.add_argument(
        '-o', '--oed_dir', metavar='N', type=str, default=None, required=False,
        help='The directory containing the set of OED exposure data files.')
    parser.add_argument(
        '-l', '--loss_factor', metavar='N', type=float, default=1.0,
        help='The loss factor to apply to TIVs.')
    parser.add_argument(
       '-d', '--debug', action='store', default=None,
       help='Store Debugging Logs under ./logs')

    args = parser.parse_args()

    run_name = args.name
    oed_dir = args.oed_dir
    loss_factor = args.loss_factor
    logger = (setup_logger(args.debug) if args.debug else None)

    (account_df, location_df, ri_info_df, ri_scope_df, do_reinsurance) = load_oed_dfs(oed_dir)

    net_losses = run_test(
        run_name,
        account_df, location_df, ri_info_df, ri_scope_df,
        loss_factor,
        do_reinsurance,
        logger)

    for (description, net_loss) in net_losses.items():
        #Print / Write Output to csv
        filename = '{}_output.csv'.format(description.replace(' ', '_'))
        net_loss.to_csv(os.path.join(run_name, filename), index=False)
        print(description)
        print(tabulate(net_loss, headers='keys', tablefmt='psql', floatfmt=".2f"))

        # print / write, output sum by location_number
        if 'loss_net' in net_loss.columns:
            loc_sum_df = net_loss.groupby(['location_number']).sum()
            filename = '{}_output_locsum.csv'.format(description.replace(' ', '_'))
            loc_sum_df.to_csv(os.path.join(run_name, filename), index=False)
            print(tabulate(loc_sum_df[['tiv','loss_pre', 'loss_net']], 
                  headers='keys', tablefmt='psql', floatfmt=".2f"))

        if args.debug:
            logger.debug(description)
            logger.debug(tabulate(net_loss, headers='keys', tablefmt='psql', floatfmt=".2f"))
        print("")
        print("")
