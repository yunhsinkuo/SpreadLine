from datetime import datetime, timedelta
import numpy as np
import pandas as pd

def _check_validity(receipient: pd.DataFrame, config: dict, rules: list[str]):
    if not set(rules).issubset(set(config.keys())):
        raise KeyError("Unmatched keys in the config")
    if not set(config.values()).issubset(set(receipient.columns)):
        raise ValueError("Unmatched values in the config")
    inv_config = {val: key for key, val in config.items()}
    receipient.rename(columns=inv_config, inplace=True)
    receipient.drop_duplicates(inplace=True)
    return receipient

# Generate the extents of the dates
def str_to_datetime(time: str, timeformat: str):
    return datetime.strptime(time, timeformat)

def datetime_to_str(time: datetime, timeformat: str):
    return time.strftime(timeformat)

#  Generate the array of dates given the above extents
def get_time_array(extents: list[str], timeDelta: str, timeformat: str) -> list[str]:
    if timeDelta == 'year':
        return [ str(year) for year in range(int(extents[0]), int(extents[1]) + 2) ]
    start = datetime.strptime(extents[0], timeformat)
    end = datetime.strptime(extents[1], timeformat)
    if timeDelta == 'month':
        months = (end.year - start.year) * 12 + end.month - start.month
        return [ datetime_to_str((start + timedelta(months=idx)), timeformat) for idx in range(months + 2) ]
    delta = end - start
    # + 2 means for 10 days we give 11 points back, the last point should not be rendered but helps aggregation
    if timeDelta == 'hour':
        hours, _ = divmod(delta.seconds, 3600)
        return [ datetime_to_str((start + timedelta(hours=idx)), timeformat) for idx in range(hours + 2) ]
    if timeDelta == 'week':
        weeks, _ = divmod(delta.days, 7)
        return [ datetime_to_str((start + timedelta(weeks=idx)), timeformat) for idx in range(weeks + 2) ]
    #NOTE: above are figuratively, it might need updates 
    if timeDelta == 'day':
        return [ datetime_to_str((start + timedelta(days=idx)), timeformat) for idx in range(delta.days + 2)]
    raise KeyError("The given delta is not supported")

def _sparse_argsort(arr: np.ndarray) -> np.ndarray:
    """
    Order the array indices based on their value in an ascending order, excluding the zero elements.
    i.e., this returns the sorted entity ids/indices based on their ordering.
    """
    nonzeroIndices = np.nonzero(arr)[0]
    return nonzeroIndices[np.argsort(arr[nonzeroIndices])]