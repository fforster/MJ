import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
sns.set(style="whitegrid")
import re

import matplotlib.patches as mpatches
from matplotlib.legend_handler import HandlerPatch

class HandlerEllipse(HandlerPatch):
    def create_artists(self, legend, orig_handle,
                       xdescent, ydescent, width, height, fontsize, trans):
        center = 0.5 * width - 0.5 * xdescent, 0.5 * height - 0.5 * ydescent
        p = mpatches.Ellipse(xy=center, width=1.7 * height + xdescent,
                             height=1.7 * height + ydescent)
        self.update_prop(p, orig_handle, legend)
        p.set_transform(trans)
        return [p]


class MJ(object):

    # initialize data
    def __init__(self, evaluations, order, colors, threshold, verbose=False):

        self.evaluations = evaluations
        self.order = order
        self.colors = colors
        self.threshold = threshold

        # remove non questions
        self.evaluations = self.evaluations[[col for col in list(self.evaluations) if re.search(".*\s\[.*\]", col) ]].copy()
        
        # Fill missing values with the lowest evaluation
        self.evaluations.fillna(order[0], inplace=True)

        # get questions
        self.options = list(self.evaluations)

        # get questions
        self.questions = np.unique(np.array([option[:option.index("[")-1] for option in self.options]))

        if verbose:
            print("Questions:")
            print(self.questions)

        # populate dictionary of results
        self.results = {}
        for question in self.questions:
            self.results[question] = pd.DataFrame()
            if verbose:
                print(question)
            for option in self.options:
                if question in option:
                    aux = option[len(question)+2:-1]
                    self.results[question] = pd.concat([self.results[question], self.evaluations[option]], axis=1)
            if verbose:
                display(self.results[question])

        # replace evaluations by numbers
        for idx, val in enumerate(self.order):
            for question in self.questions:
                self.results[question].replace(val, idx, inplace=True)
            
        # names
        self.names = {}
        for question in self.questions:
            self.names[question] = [col[len(question)+2:-1] for col in list(self.results[question])]

    # sort evaluations
    def sortMJ(self, question, verbose=False):
        
        dfsel = self.results[question].copy()
                
        # compute quantiles and q and p values
        perc = {}
        perc_vals = {}
        qs = {}
        ps = {}
        suffix = {}
        for name in list(dfsel):
            perc_vals[name] = np.percentile(dfsel[name], 100 - self.threshold)
            ps[name] = (dfsel[name] > perc_vals[name]).sum() / dfsel.shape[0]
            qs[name] = (dfsel[name] < perc_vals[name]).sum() / dfsel.shape[0]
        
            z = self.threshold / 100.
            if ps[name] / z > qs[name] / (1 - z): # notar esta modificación para percentiles diferentes de 50
                suffix[name] = 1
            else:
                suffix[name] = -1
            perc[name] = self.order[int(perc_vals[name])]
            
            if verbose:
                print(name)
                print("   p=%.3f, %s, q=%.3f" % (ps[name], perc[name] + ("+" if suffix[name] == 1 else '-'), qs[name]))
                
        # Convertir a numpy array y crear pandas dataframe
        data = np.array([list(perc_vals.values()), list(ps.values()), list(qs.values()), list(suffix.values()), list(perc.values())])
        result = pd.DataFrame(data=data.transpose(), index=list(dfsel), columns=["perc_val", "p", "q", "suffix", "perc"])
        
        # add short names
        result["Name"] = self.names[question]
        
        # asegurarse que columnas tengas valores numéricos
        result[["perc_val", "p", "q", "suffix"]] = result[["perc_val", "p", "q", "suffix"]].apply(pd.to_numeric, errors='ignore', axis=1)
        
        # crear columna que se usará para hacer comparación (resultado menor es mejor)
        result["comp"] = result.apply(lambda row: row.q if row.suffix == -1 else -row.p, axis=1)
        
        # ordenar valores:
        # 1. primero según el valor del percentil solicitado en orden descendiente,
        # 2. si valores son iguales, según sufijo en orden descendiente, 
        # 3. si valores son iguales, según valor de comparación en orden ascendente:
        #     si p es mayor que q, mayor p tiene prioridad
        #     si p es menor que q, menor q tiene prioridad
        result = result.sort_values(['perc_val', 'suffix', 'comp'], ascending=[False, False, True])

        return result

    # find lower middle most index
    def lmmidx(self, n):
        return int(n/2 - 1 + n%2/2)
    

    # compare two rows manually
    # return 1 if col1 > col2, 0 if they are the same, -1 otherwise
    def compare(self, col1, col2, verbose=False):
        
        col1 = np.array(col1.sort_values().tolist())
        col2 = np.array(col2.sort_values().tolist())
        lmm = self.lmmidx(len(col1))
        if verbose:
            print(col1, col2)
        while col1[lmm] == col2[lmm]:
            col1 = np.concatenate([col1[:lmm], col1[lmm+1:]])
            col2 = np.concatenate([col2[:lmm], col2[lmm+1:]])
            lmm = self.lmmidx(len(col1))
            if len(col1) == 1:
                break
            if verbose:
                print("-->", col1, col2)
        return np.sign(col1[lmm] - col2[lmm])


    # swap two rows
    def swap_rows(self, df, row1, row2):
        
        df.iloc[row1], df.iloc[row2] =  df.iloc[row2].copy(), df.iloc[row1].copy()
        idx1 = df.index[row1]
        idx2 = df.index[row2]
        idx = list(df.index)
        idx[row1] = idx2
        idx[row2] = idx1

        return pd.DataFrame(data=df.values, columns=list(df), index=idx)


    # fix dataframe
    def fix(self, result, question, verbose=False):
    
       if self.threshold != 50:
           print("Warning: fix function not implemented for sub/supramajority")
           return False
       comp = 0
       for idx in range(result.shape[0] - 1):
           name1 = f"{question} [{result.Name.iloc[idx]}]"
           name2 = f"{question} [{result.Name.iloc[idx+1]}]"
           #print(name1, name2)
           comp = self.compare(self.results[question][name1],
                               self.results[question][name2],
                               verbose)
           if comp < 0:
               print(f"--> Warning: {result.Name.iloc[idx]}, {result.Name.iloc[idx+1]}")
               return self.fix(self.swap_rows(result, idx, idx+1), question, verbose)
       return result

    # visualize ranked options
    def viz(self, result, question):

        dfsel = self.results[question].copy()
       
        # agregar columnas con porcentaje acumulado desde mayor a menor
        for val in range(len(self.order)):
            result[str(int(val))] = ((dfsel>=val).sum(axis=0)) / dfsel.shape[0] * 100
    
        # inicializar gráfico
        fig, ax = plt.subplots(figsize=(14, 9))
        sns.set_color_codes("pastel")
        
        # barras
        for idx in range(len(self.order)):
            label = self.order[idx]
            sns.barplot(x=str(idx), y="Name", data=result,
                    label=label, color=self.colors[idx], linewidth=0)
        
        # círculos
        handles, labels = ax.get_legend_handles_labels()
        for i in range(len(self.order)):
            handles[i] = mpatches.Circle(handles[i][0].get_xy(), 0.25, facecolor=handles[i][0].get_facecolor(),
                            edgecolor="white", linewidth=1)
            labels[i] = labels[i]
        ax.legend(handles[::-1], labels[::-1], ncol=3, bbox_to_anchor=(1.1, 1.24), frameon=False, fontsize=19, 
                 handler_map={mpatches.Circle: HandlerEllipse()})
        
        # ticks
        for tick in ax.yaxis.get_major_ticks():
            tick.label.set_fontsize(20) 
        for tick in ax.xaxis.get_major_ticks():
            tick.label.set_fontsize(20) 
            
        # ejes
        ax.axvline(self.threshold,  c='white')
        ax.set_xlabel("% evaluations", fontsize=20)
        ax.set_ylabel("", fontsize=14)
        ax.set_xlim(0, 100)
        ax.grid(False)
        ax.spines['bottom'].set_color('white')
        ax.spines['top'].set_color('white') 
        ax.spines['right'].set_color('white')
        ax.spines['left'].set_color('white')
        ax.set_title(question, fontsize=24)
        plt.tight_layout()
        plt.show()

    # sort all questions
    def sortMJall(self, fix=False, verbose=False):

        for question in self.questions:

            # sort given question
            result = self.sortMJ(question, verbose)

            # fix sorted data (use when some options have zero votes)
            if fix:
                result = self.fix(result, question, verbose)

            # visualize results    
            self.viz(result, question)

            # show sorted dataframe
            display(result)
