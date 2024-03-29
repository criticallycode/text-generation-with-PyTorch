import unidecode
import string
import random
import torch
import torch.nn as nn
from torch.autograd import Variable
import time, math
from torch.optim.lr_scheduler import ReduceLROnPlateau

# begin by converting any unicode characters in the text into ASCII, with unidecode

def text_preprocess(text_file):
    # get all printable characters
    print_charas = string.printable
    num_charas = len(print_charas)

    # print(print_charas)

    text_data = unidecode.unidecode(open(text_file, encoding="ISO-8859-1").read())

    # figure our the length of the file
    # this is important as we will be splitting the text file up into random chunks

    len_text = len(text_data)
    print(len_text)

    return print_charas, num_charas, text_data, len_text

printable, num_charas, text_file, text_len = text_preprocess("Horror_plots_2_correct.txt")

# need to split the text file into chunks
# create a function to get random chunks that will be used as input for the network

# specify the length of the chunk

chunk_len = 200

def get_rand_chunk():
    # select a random starting point from the beginning
    # of the file until the end minus chunk len
    start_idx = random.randint(0, text_len - chunk_len)
    # specify the end point
    end_idx = start_idx + chunk_len + 1
    return text_file[start_idx:end_idx]

# check to see if function works
print(get_rand_chunk())

# now it is time to define the RNN
# internal structure of the net is like this: encoding layers, GRU layer
# decoder layer

# inherit from nn.Module
class RNN(nn.Module):
    # initialize the class with chosen arguments
    def __init__(self, in_size, hidden_size, out_size, num_layers=1, drop_prob=0.5):
        # make sure to inherit from the base RNN class
        super(RNN, self).__init__()
        self.in_size = in_size
        self.hidden_size = hidden_size
        self.out_size = out_size
        self.num_layers = num_layers

        # define the layers
        self.encoder = nn.Embedding(in_size, hidden_size)
        # hidden size is both input and output here, since we aren't changing the size
        # of the input inbetween layers, also takes num layers
        self.gru = nn.GRU(hidden_size, hidden_size, num_layers)
        # our purput layer is a linerar layer, will take in hidden size and returns output size
        self.decoder = nn.Linear(hidden_size, out_size)
        self.dropout = nn.Dropout(drop_prob)

    # now we have to define the forward training pass

    def forward(self, input, hidden):
        # input will be the encodings generated by the encoder, transformed into tensors by view
        input = self.encoder(input.view(1, -1))
        input = self.dropout(input)
        # view changes 1 x 1, to length of given sequence
        output, hidden = self.gru(input.view(1, 1, -1), hidden)
        output = self.decoder(output.view(1, -1))
        return output, hidden

    # time to define a function to zero states on creation
    def init_hidden(self):
        # return a variable full of all zeroes
        return Variable(torch.zeros(self.num_layers, 1, self.hidden_size))

# going to create a long tensor out of every chunk, accomplish this by looping through
# characters and getting index of every character
def chunk_tensor(input):
    # initialize the tensor with length of input string
    tensor = torch.zeros(len(input)).long()
    # for every character in the input string
    for i in range(len(input)):
        # get the index of the character from the list of printable characters
        tensor[i] = printable.index(input[i])
    tensor = Variable(tensor)
    return tensor


# now we need to create a training set for the network
# we want the input to be every character except the last,
# while the target should be every charcter except the first

def create_training_set():
    # make a random chunk
    chunk = get_rand_chunk()
    inp = chunk_tensor(chunk[:-1])
    target = chunk_tensor(chunk[1:])
    return inp, target

# now we need to evaluate the network
# we'll give one character at a time to the network
# the network has given us a probability distribution for the next character in the sequence
# repeat this process until the end of the string

# in order to generate text, we need to feed the network a priming string
# so it can begin building up a hidden state,
# after probabilities are returned we generate one character at a time

# define out priming string, the length of text we want to predict, and the temperature
def model_evaluate(prime_str='A', predict_len=100, temp=0.8):

    # start off by giving the network a hidden layer with zeroed states
    hidden = decoder.init_hidden()
    prime_input = chunk_tensor(prime_str)
    predicted = prime_str

    # need to build up hidden state, start off with the priming string
    for c in range(len(prime_str) - 1):
        # return the current hidden state
        _, hidden = decoder(prime_input[c], hidden)

    # make the input whatever the character tensor has generated based on the prime string
    inp = prime_input[-1]

    for p in range(predict_len):
        # use the decoder and get output and hidden values
        output, hidden = decoder(inp, hidden)

        # Sample from the network as a multinomial distribution
        # convert the output data to a tensor with view
        # divided by chosen temperature, exp returns exponential
        output_dist = output.data.view(-1).div(temp).exp()
        # convert into a multinomial
        top_i = torch.multinomial(output_dist, 1)[0]

        # now append the predicted character to the string and use that string as the
        # next input into the network
        predicted_char = printable[top_i]
        predicted += predicted_char
        inp = chunk_tensor(predicted_char)

    return predicted

# this function just prints the amount of time passed during training

def get_time(passed):
    sec = time.time() - passed
    # round down to nearest minute
    minute = math.floor(sec/60)
    sec -= minute * 60
    return '%dm %ds' % (minute, sec)

# now we need to define the training function

def train_loop(input_data, target):

    # initialize hidden state
    hidden = decoder.init_hidden()
    # zero the gradients at the start
    decoder.zero_grad()
    # set loss to zero
    loss = 0

    # for every character in the chunk length
    # get the output of the model and the hidden state
    for char in range(chunk_len):
        output, hidden = decoder(input_data[char], hidden)
        # update the loss, need to unsqueeze it
        loss += criterion(output, target[char].unsqueeze(0))

    # do the backprop
    loss.backward()
    # do a step of optimization
    decoder_optimizer.step()

    # return the first element of the loss divided by chunk length
    # call the item function to get the item of the data
    return loss.data.item()/ chunk_len


# now we have to declare the training parameters
num_epochs = 200
print_delay = 100
plot_delay = 100

hidden_size = 100
num_layers = 2
learning_rate = 0.002

# what will we use as the decoder, the RNN
decoder = RNN(num_charas, hidden_size, num_charas, num_layers, drop_prob=0.2)
# choose the optimizer
decoder_optimizer = torch.optim.Adam(decoder.parameters(), lr=learning_rate)

# declare the criterion we will use to calculate the loss
criterion = nn.CrossEntropyLoss()

def train_and_generate(num_epochs, print_delay, plot_delay):

    start = time.time()
    total_loss = []
    avg_loss = 0

    # print the loss and generate text
    # for the epochs in the total number of epochs + 1
    for epoch in range(1, num_epochs + 1):
        loss = train_loop(*create_training_set())
        avg_loss += loss

        if epoch % print_delay == 0:
            # if epoch num divisible without remainders:
            # print the running time divided by number of epochs
            print("Current running time: " + get_time(start))
            print("Epoch:{}, Percent complete: {}%, Loss: {}".format(epoch, epoch/num_epochs*100, loss))
            #print('[%s (%d %d%%) %.4f]' % (get_time(start), epoch, epoch / num_epochs * 100, loss))
            # this prints the characters that have their probability evaluated
            print(model_evaluate('a', 200), '\n')

        if epoch % plot_delay == 0:
            total_loss.append(avg_loss / plot_delay)
            avg_loss = 0

    torch.save(decoder.state_dict(), "./textgen_model_1.pth")

train_and_generate(num_epochs, print_delay, plot_delay)


def text_gen(prime_str='A', predict_len=100, temp=0.8):
    decoder = RNN(num_charas, hidden_size, num_charas, num_layers, drop_prob=0.2)
    decoder.load_state_dict(torch.load("./textgen_model_1.pth"))

    # start off by giving the network a hidden layer with zeroed states
    hidden = decoder.init_hidden()
    prime_input = chunk_tensor(prime_str)
    predicted = prime_str

    # need to build up hidden state, start off with the priming string
    for c in range(len(prime_str) - 1):
        # return the current hidden state
        _, hidden = decoder(prime_input[c], hidden)

    # make the input whatever the character tensor has generated based on the prime string
    inp = prime_input[-1]

    for p in range(predict_len):
        # use the decoder and get output and hidden values
        output, hidden = decoder(inp, hidden)

        # Sample from the network as a multinomial distribution
        # convert the output data to a tensor with view
        # divided by chosen temperature, exp returns exponential
        output_dist = output.data.view(-1).div(temp).exp()
        # convert into a multinomial
        top_i = torch.multinomial(output_dist, 1)[0]

        # now append the predicted character to the string and use that string as the
        # next input into the network
        predicted_char = printable[top_i]
        predicted += predicted_char
        inp = chunk_tensor(predicted_char)

    print("Generated text is:")
    print(predicted)

text_gen()
