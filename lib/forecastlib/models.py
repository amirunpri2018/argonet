''' models.py

Contains the template for Geo_model, a class that includes all variables and methods for
running an ARGO (AutoRegressive model with General Online information) prediction over
a specific geographical location.

The steps for running a Geo_model are:

1. Loading input data
    This is performed by the data_load() method and returns three instance variables:
        target = gold standard array
        inputs = independent variables
        datelist = list of dates associated with the above time series.
    Specific loading functions can be found in loading_functions.py

2. Initializing predictors
    Geo_model can fire off multiple Predictor objects, each loaded with the input data.
    Each predictor can perform a different ARGO model with its own transforms and methodology.

    The init_predictor() method creates a single Predictor object and can be iterated.
    The init_prediction_layer() is a built-in iterator that initializes predictors,
    processes their data, and generates predictions in a single call.

3. Processing input
    Each Predictor object can process the input data in its own way, as specified by the user.
    This is performed by the data_process() method in the Predictor class, with supporting
    functions in processing_functions.py

4. Running model
    Like processing, can run a different, user-specified model on each Predictor object.
    This is performed by the predict() method for each Predictor object.
    The model implementations can be found in argo_functions.py

5. (Optional) Ensemble model
    After each Predictor object has completed, their predictions can be used to form an ensemble
    model. See ensemble() for specifications.

6. Save outputs
    Calling the save_predictions() method outputs a csv with predictions generated by Geo_model.

'''

import datetime
import numpy as np
import pandas as pd
import copy

import loading_functions
import processing_functions
import argo_class


class Geo_model(object):
    ''' defines a Geo_model, an entire model for any geographical region.

    Parameters:
    geo_level: 'National', 'Regional', 'State', 'City'
        The geographical scale of the model is used to determine how to correctly
        load and process input data files.

    geo_id: e.g. 2, 'TX', 'MA', default=None
        If geo_level is 'Regional', int from 1-10.
        If 'State', two-letter state abbrev.
        If 'City', city name, etc.

    resolution: 'week', 'month', default='week'
        Specify whether to make weekly or monthly predictions. Must match input data.

    pred_start_date: 'YYYY-MM-DD'
        Date of first prediction to be generated i.e. the first row in the prediction csv
        will be the week or month starting on pred_start_date.

        If resolution is 'week', then pred_start_date should be a week starting Sunday.
        If resolution is 'month', then pred_start_date should be the first day of the month,
        e.g. '2008-05-01'.

    use_data_from: 'YYYY-MM-DD', default='2010-01-03'
        Date of first data to collect for the model, used to align all input data together.
        Data from before this date is discarded to save memory.

        If resolution is 'week', then use_data_from should be a week starting Sunday.
        If resolution is 'month', then use_data_from should be the first day of the month,
        e.g. '2008-05-01'.
    '''

    def __init__(self, geo_level, geo_id=None, resolution='week', pred_start_date='2013-01-06',
                 use_data_from='2010-01-03', verbose=True):
        ''' initializes a Geo_model object.
            self.inputs is a dictionary that will store the input variables;
            self.target will hold the target time series;
            self.datelist stores the dates associated with the time series
            self.model_list will store the predictor objects
            '''

        self.geo_level = geo_level
        self.geo_id = geo_id
        self.resolution = resolution
        self.pred_start_date = pred_start_date
        self.use_data_from = use_data_from
        self.verbose = verbose

        self.inputs = {}
        self.target = None
        self.datelist = None
        self.model_list = []

        print '\n----------------------START-----------------------'
        print datetime.datetime.now()
        print self.geo_level + ' Geo_model initialized.'
        if self.verbose is True:
            print '\tgeo_id: ', self.geo_id, '\n\tresolution: ', self.resolution
            print '\tpred_start_date: ', self.pred_start_date, '\n\tuse_data_from: ', self.use_data_from

    def data_load(self, target_file=None, gt_file=None, ath_file=None, fny_file=None):
        ''' loads data from raw data files when available, using user-specified locations.

        Parameters:
            target_file: location of gold standard csv

            gt_file: location of Google Trends csv

            ath_file: location of Athenahealth csv

            fny_file: location of FNY csv

        Date columns are automatically processed, and the returned data arrays
        will start from use_data_from parameter.

        Also creates datelist which is the time variable associated with the data series.

        Functions are found in loading_functions.py
        '''
        if self.verbose is True:
            print 'Loading data sources:'

        self.target = loading_functions.load_target(file_loc=target_file, geo_level=self.geo_level,
                                                    geo_id=self.geo_id, use_data_from=self.use_data_from)
        if gt_file:
            try:
                self.inputs['gt'] = loading_functions.load_gt(file_loc=gt_file, use_data_from=self.use_data_from)
            except Exception as e:
                print 'Error loading GT. ', e

        if ath_file:
            try:
                self.inputs['ath'] = loading_functions.load_athena(file_loc=ath_file, geo_level=self.geo_level,
                    geo_id=self.geo_id, use_data_from=self.use_data_from, smoothing=None)
            except Exception as e:
                print 'Error loading ath. ', e

        if fny_file:
            try:
                self.inputs['fny'] = loading_functions.load_fny(file_loc=fny_file, use_data_from=self.use_data_from)
            except Exception as e:
                print 'Error loading FNY. ', e

        # makes sure length of inputs is 1 longer than length of target
        self.inputs, self.target = loading_functions.validate_vars(self.inputs, self.target)

        # create datelist based on use_data_from and the lengths of input variables
        self.datelist = loading_functions.create_datelist(self.inputs, self.target, self.use_data_from, self.resolution)

    def data_load_from_file(self, file_loc, date_col, target_col, **otherdata):

        self.target, self.inputs, first_date = loading_functions.load_singlefile(file_loc, date_col, target_col, **otherdata)
        self.datelist = loading_functions.create_datelist(self.inputs, self.target, first_date, self.resolution)

    def init_predictor(self, label):
        ''' creates a single Predictor object and returns it

            Parameters:
                label: Name of the predictor, used as unique identifier, e.g. 'ARGO (t-1)'.
        '''

        model = Predictor(copy.deepcopy(self.inputs), np.copy(self.target), label, self.pred_start_date,
                          copy.copy(self.datelist), self.resolution, self.verbose)
        self.model_list.append(model)

        return model

    def init_prediction_layer(self, n_models, labels, process_specs, predict_specs):
        ''' iterator for initializing a layer of predictors, processing them, and making predictions.

            Parameters:
                n_models: Number of Predictor objects to create

                labels: List of names for the predictors

                process_specs: Function arguments for Predictor.data_process() for each predictor.
                    Pass in the form of a 2-D list, with each predictors as rows.

                predict_specs: Function arguments for Predictor.predict() for each predictor.
                    Same input format as process_specs
        '''

        self.model_list = [Predictor(copy.deepcopy(self.inputs), np.copy(self.target), labels[i], self.pred_start_date,
                           copy.copy(self.datelist), self.resolution, self.verbose) for i in range(n_models)]

        for i in range(len(self.model_list)):
            self.model_list[i].data_process(*process_specs[i])
            self.model_list[i].predict(*predict_specs[i])

    def ensemble(self, method, ens_label, ind_labels, horizon=0, train_len=104, in_sample=False):
        ''' Runs an ensemble model on previously made prediction models within the same Geo_model.

            Parameters:
                method: 'ARGO', 'median', etc.

                ens_label: Identifier for the ensemble model

                ind_labels: List of identifiers for the input models to the ensemble

                horizon: T-1 to T+2 correspond to 0 to 3.
                    This should match the horizon of the input models. For example, if running an ensemble
                    on a set of individual predictors on T+1 horizon, set this to 2 for proper training.

                train_len: dynamic training window size. Some models, such as the median, do not require
                    training sets and may ignore this setting. However, they may still discard the first
                    train_len values from the prediction to be consistent with models with training windows.
                    Please check the specific model implementation in argo_functions.py to be sure.

                    This value will still be used to update the target variable, however, so should be
                    set to a value consistent with the specific model's prediction output.

                in_sample: Specifies whether to produce in_sample predictions.
                    Note that the input models for the ensemble may often include in_sample predictions,
                    which basically uses the first n in_sample predictions from the input models
                    in the ensemble, where n = train_len of the input models. This can be done
                    when there is not enough time series data to train completely out-of-sample on both
                    input and ensemble models.
        '''
        if self.verbose is True:
            print 'Running ensemble model: ', method

        # make a list of the models to use in ensemble, indexing based on horizon to remove nans.
        compat_list = [m for m in self.model_list if m.label in ind_labels]
        compat_pred_list = [x.predictions[2 * horizon:, None] for x in compat_list]

        # form a matrix of the input model predictions and get a copy of the target and datelist
        model_stack = np.hstack(compat_pred_list)
        ens_target = compat_list[0].target
        ens_datelist = compat_list[0].datelist

        # run specified ensemble model
        ens_pred = argo_functions.ensemble_dispatcher[method](model_stack, ens_target, horizon,
                                                              training=train_len, in_sample=in_sample)

        # index train_len into target to align with prediction array
        if in_sample is not True:
            ens_target = ens_target[train_len:]
            ens_datelist = ens_datelist[train_len:]

        # insert nans for skipped weeks in T horizon and up
        ens_pred = np.insert(ens_pred, 0, [np.nan] * horizon * 2)

        # report performance
        argo_functions.metrics(ens_pred[2 * horizon:-(1 + horizon)], ens_target[2 * horizon:])

        # add ensemble predictor to model list
        self.model_list.append(Ens_predictor(target=ens_target, predictions=ens_pred,
                                             label=ens_label, datelist=ens_datelist))

    def save_predictions(self, fname, model_labels='all', end_saturday=True):
        ''' Saves predictions from self.model_list to a csv file

            Parameters:
                fname: str. Output file name

                model_labels: 'all', or list of models to print out.

                end_saturday: bool.
                    Specifies whether to represent weeks by beginning Sunday or ending Saturday.
                    Set to False for monthly predictions, as it will not change the dates.
        '''
        if self.verbose is True:
            print 'Saving predictions to file. '

        # create list of models matching model_labels, or if 'all' include all models
        if model_labels == 'all':
            s = [m for m in self.model_list]
        else:
            try:
                s = [m for m in self.model_list if m.label in model_labels]
            except:
                s = [m for m in self.model_list]
                print "\tError in specified model labels. Printing all models to file."

        # index all model variables so that they start with user-specified prediction start date
        preds = []
        for model in s:
            shift = model.datelist.index(pd.to_datetime(self.pred_start_date))
            model.datelist = model.datelist[shift:]
            model.target = model.target[shift:]
            model.predictions = model.predictions[shift:]
            preds.append(pd.Series(model.predictions, name=model.label))

        # extract datelist from the first model, optionally converting to Saturdays
        tmp = s[0].datelist
        if end_saturday is True:
            tmp = [x + datetime.timedelta(6) for x in tmp]
        time = pd.Series(tmp, name='week')

        # extract target time series from the first model
        targ = pd.Series(s[0].target, name='target')

        # concatenate into dataframe and output as csv
        df = pd.concat([time, targ] + preds, axis=1)
        df.to_csv(fname, index=False, date_format='%Y-%m-%d')

        print '\n', datetime.datetime.now()
        print '----------------------END-----------------------'


class Predictor(object):
    ''' Defines a specific capsule that runs a single prediction after being loaded with data by Geo_model.
    '''

    def __init__(self, geo_model_inputs, target, label, start_date, datelist, resolution, verbose):
        self.X = geo_model_inputs
        self.target = target
        self.target_reserve = np.copy(self.target)
        self.label = label
        self.start_date = start_date
        self.datelist = datelist
        self.resolution = resolution
        self.verbose = verbose

        self.transform_target = False
        self.predictions = None

        print '-------------------------------------------------'
        print 'Predictor object initialized: ', label

    def data_process(self, transform_target=False, transform_ath=False, transform_gt=False, AR_terms='None'):
        ''' Processes and transforms data.

            Parameters:
                transform_target: Bool. Whether the logit-transform of the target data is used.

                transform_ath: Bool. Whether the logit-transform of the athenahealth data is used.

                transform_gt: Bool. Whether the log-transform of the Google Trends data is used.

                AR_terms: None or int. Number of auto-regressive target terms to use as predictors.
        '''
        if self.verbose is True:
            print 'Processing data for ' + self.label + ': '

        if transform_target:
            try:
                self.target = processing_functions.logit_percent(self.target)
                self.transform_target = True
                if self.verbose is True:
                    print '\tTarget transformed.'
            except Exception as e:
                print '\tError: target may contain 0 or NaNs.', e
                self.transform_target = False

        if transform_ath and 'ath' in self.X:
            try:
                self.X['ath'] = processing_functions.logit_percent(self.X['ath'])
                if self.verbose is True:
                    print '\tAthenahealth transformed.'
            except Exception as e:
                print '\tError: athenahealth data may contain 0 or NaNs.', e

        if transform_gt and 'gt' in self.X:
            try:
                self.X['gt'] = processing_functions.gtlog(self.X['gt'])
                if self.verbose is True:
                    print '\tGoogle Trends transformed.'
            except Exception as e:
                print '\tError: GT data may contain 0 or NaNs.', e

        if AR_terms:
            # discard first 'AR_terms' rows from other variables to shift for AR matrix
            discard = AR_terms if isinstance(AR_terms, (int, long)) else max(AR_terms)
            for key in self.X:
                self.X[key] = self.X[key][discard:]
            self.datelist = self.datelist[discard:]
            # TO-DO: code exception

            # create AR matrix from the target time series
            try:
                self.X['ar'] = processing_functions.create_ar_stack(self.target, AR_terms)

                # if 'ar' is not the only data, potentially shorten by 1 to match length of other inputs
                while len(self.X.keys()) > 1:
                    other_key = self.X.keys().pop(0)
                    if other_key != 'ar':
                        self.X['ar'] = self.X['ar'][:len(self.X[other_key])]
                        break
                if self.verbose is True:
                    print '\tAR' + str(AR_terms) + ' matrix created.'
            except Exception as e:
                print 'Error: AR matrix creation unsuccessful.', e

            # discard first 'AR_terms' from target after AR matrix is created
            self.target = self.target[discard:]
            self.target_reserve = self.target_reserve[discard:]

    def predict(self, input_vars='all', method='ARGO', horizon=0, train_len='default', in_sample=False, **params):
        ''' Runs prediction algorithm on the processed data sources.

            Parameters:
                inputs: 'all' or a list of elements, e.g. ['ath','gt','ar'].

                method: 'ARGO', 'SVM', etc.

                start_date: first week of prediction

                horizon: integer from 0 to 3 corresponding to T-1 to T+2 respectively.

                train_len: integer for width of training window.
                    Defaults to 104 if resolution is week, 24 if resolution is month.

                **params: additional inputs that can be dynamically specified to match
                    method-specific parameters, e.g. in_sample, filter_corr, normalize.
                    See method-specific specifications in argo_functions.py
        '''
        if self.verbose is True:
            print 'Running method for ' + self.label + ': ', method

        ###### Pre-prediction processing ######

        # stack independent variables together based on user input
        if input_vars == 'all':
            X_stack = np.hstack([self.X['ath'], self.X['gt'], self.X['ar']])
        else:
            X_stack = np.hstack([self.X[term] for term in input_vars])

        # define default training window width
        if train_len == 'default':
            if self.resolution == 'week':
                train_len = 104
            elif self.resolution == 'month':
                train_len = 24

        # re-index variables so that first prediction is on user-supplied start_date
        # exception is if in_sample is specified: then first prediction is on the
        # first training date.
        shift = self.datelist.index(pd.to_datetime(self.start_date))
        shift_vars = shift - train_len
        shift_dates = shift - train_len * in_sample
        assert (shift_vars >= 0), '\tError: Not enough data before prediction start date'

        if self.verbose is True:
            if in_sample:
                print '\tFirst in sample prediction: ', self.datelist[shift_dates]
            print '\tFirst out of sample prediction: ', self.datelist[shift]

        # index the vars to start with correct date
        X_stack = X_stack[shift_vars:]
        self.target = self.target[shift_vars:]
        self.target_reserve = self.target_reserve[shift_vars:]
        self.datelist = self.datelist[shift_dates:]

        ###### Run prediction ######
        if self.verbose is True:
            print '\tTarget length: ' + str(len(self.target)) + '\tPredictor length: ' + str(len(X_stack))
            print '\tPrediction length: ', str(len(self.datelist) + (horizon - 3))

        argo = argo_class.ARGO(X_stack, self.target, self.transform_target)
        self.predictions = argo.make_predictions(method, horizon, training=train_len,
                                                 in_sample=in_sample, **params)

        ###### Post-prediction processing ######

        # undoing transform if present, checking that it restores the original
        if self.transform_target:
            self.predictions = processing_functions.inverse_logit_percent(self.predictions)
            self.target = processing_functions.inverse_logit_percent(self.target)

            # assert np.allclose(self.target, self.target_reserve), 'Error: Inverse target transform'

        # index train_len into target to align with prediction array
        if in_sample is not True:
            self.target = self.target[train_len:]

        # insert nans for skipped weeks in T horizon and up
        self.predictions = np.insert(self.predictions, 0, [np.nan] * (horizon * 2))

        # report performance
        try:
            argo_functions.metrics(self.predictions[2 * horizon:-(1 + horizon)], self.target[2 * horizon:])
        except:
            'Metric reporting error.'

        if self.verbose is True:
            print 'Prediction complete.'
            print '-------------------------------------------------'


class Ens_predictor:
    ''' Generic predictor object for ensemble method that disguises
        itself as a Predictor object in Geo_model.model_list.
    '''

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)