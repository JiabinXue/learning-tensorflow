import os 
import random
import numpy as np
import tensorflow as tf
from PIL import Image
import getpass

import scipy.misc as misc

CELEBA_DATE_DIR = '/home/%s/data/CelebA/Img/img_align_celeba' % getpass.getuser()
batch_size = 64
IMAGE_SIZE = 64
IMAGE_CHANNEL = 3

train_images = []
num_batch = 0

# jilv training images
for image_filename in os.listdir(CELEBA_DATE_DIR):
    if image_filename.endswith('.jpg'):
        train_images.append(os.path.join(CELEBA_DATE_DIR, image_filename))

random.shuffle(train_images)

num_batch = len(train_images) // batch_size



def get_next_batch(pointer):
    image_batch = []
    images = train_images[pointer * batch_size: (pointer + 1) * batch_size]
    for img in images:
        arr = Image.open(img)
        arr = arr.resize((IMAGE_SIZE, IMAGE_SIZE))
        arr = np.array(arr)
        arr = arr.astype('float32') / 127.5 - 1
        image_batch.append(arr)
    return image_batch

z_dim = 100
noise = tf.placeholder(tf.float32, [None, z_dim], name='noise')

X = tf.placeholder(tf.float32, [batch_size, IMAGE_SIZE, IMAGE_SIZE, IMAGE_CHANNEL], name='x')

train_phase = tf.placeholder(tf.bool)

def batch_norm(x, beta, gamma, phase_train, scope='bn', decay=0.9, eps=1e-5):
    with tf.variable_scope(scope):
        # moments :统计矩，mean 是一阶矩，variance 则是二阶中心矩
        batch_mean, batch_var = tf.nn.moments(x, [0, 1, 2], name='moments')
        # ExponentialMovingAverage ?
        ema = tf.train.ExponentialMovingAverage(decay=decay)

        def mean_var_with_update():
            ema_apply_op = ema.apply([batch_mean, batch_var])
            with tf.control_dependencies([ema_apply_op]):
                return tf.identity(batch_mean), tf.identity(batch_var)

        mean, var = tf.cond(phase_train, mean_var_with_update, lambda: (ema.average(batch_mean), ema.average(batch_var)))
        normed = tf.nn.batch_normalization(x, mean, var, beta, gamma, eps)

    return normed

# generator_variables_dict = {
#     "W_1": tf.Variable(tf.truncated_normal([z_dim, 2 * IMAGE_SIZE * IMAGE_SIZE], stddev=0.02), name="Generator/W_1"),
#     "b_1": tf.Variable(tf.constant(0.0, shape=[2 * IMAGE_SIZE * IMAGE_SIZE]), name='Generator/b_1'),
#     "beta_1": tf.Variable(tf.constant(0.0, shape=[512]), name='Generator/beta_1'),
#     "gamma_1": tf.Variable(tf.random_normal(shape=[512], mean=1.0, stddev=0.02), name='Generator/gamma_1'),

#     "W_2": tf.Variable(tf.truncated_normal([5, 5, 256, 512], stddev=0.02), name="Generator/W_2"),
#     "b_2": tf.Variable(tf.constant(0.0, shape=[256]), name="Generator/b_2"),
#     "beta_2": tf.Variable(tf.constant(0.0, shape=[256]), name="Generator/beta_2"),
#     "gamma_2": tf.Variable(tf.random_normal(shape=[256], mean=1.0, stddev=0.02), name="Generator/gamma_2"),

#     "W_3": tf.Variable(tf.truncated_normal([5, 5, 128, 256], stddev=0.02), name="Generator/W_3"),
#     "b_3": tf.Variable(tf.constant(0.0, shape=[128]), name="Generator/b_3"),
#     "beta_3": tf.Variable(tf.constant(0.0, shape=[128]), name="Generator/beta_3"),
#     "gamma_3": tf.Variable(tf.random_normal(shape=[128], mean=1.0, stddev=0.02), name="Generator/gamma_3"),

#     "W_4": tf.Variable(tf.truncated_normal([5, 5, 64, 128], stddev=0.02), name="Generator/W_4"),
#     "b_4": tf.Variable(tf.constant(0.0, shape=[64]), name="Generator/b_4"),
#     "beta_4": tf.Variable(tf.constant(0.0, shape=[64]), name="Generator/beta_4"),
#     "gamma_4": tf.Variable(tf.random_normal(shape=[64], mean=1.0, stddev=0.02), name="Generator/gamma_4"),

#     "W_5": tf.Variable(tf.truncated_normal([5, 5, IMAGE_CHANNEL, 64], stddev=0.02), name="Generator/W_5"),
#     "b_5": tf.Variable(tf.constant(0.0, shape=[IMAGE_CHANNEL]), name="Generator/b_5")
# }

def generator(noise):
    with tf.variable_scope("Generator"):
        with tf.variable_scope("fc-layer1"):
            weight = tf.get_variable('W', [z_dim, 2 * IMAGE_SIZE * IMAGE_SIZE], initializer=tf.truncated_normal_initializer(stddev=0.02))
            bias = tf.get_variable("b", [2 * IMAGE_SIZE * IMAGE_SIZE], initializer=tf.constant_initializer(0))
            beta = tf.get_variable("beta", [512], initializer=tf.constant_initializer(0))
            gamma = tf.get_variable("gamma", [512], initializer=tf.random_normal_initializer(mean=1.0, stddev=0.02))

            out_1 = tf.matmul(noise, weight) + bias
            out_1 = tf.reshape(out_1, [-1, IMAGE_SIZE // 16 , IMAGE_SIZE // 16, 512])
            out_1 = batch_norm(out_1, beta, gamma, train_phase)
            out_1 = tf.nn.relu(out_1, name="relu_activate")
        with tf.variable_scope("deconv-layer2"):
            out_2 = deconv_layer(out_1, [5, 5, 256, 512], [1, 2, 2, 1], [tf.shape(out_1)[0], IMAGE_SIZE // 8, IMAGE_SIZE // 8, 256], train_phase)
        with tf.variable_scope("deconv-layer3"):
            out_3 = deconv_layer(out_2, [5, 5, 128, 256], [1, 2, 2, 1], [tf.shape(out_1)[0], IMAGE_SIZE // 4, IMAGE_SIZE // 4, 128], train_phase)
        with tf.variable_scope("deconv-layer4"):
            out_4 = deconv_layer(out_3, [5, 5, 64, 128], [1, 2, 2, 1], [tf.shape(out_1)[0], IMAGE_SIZE // 2, IMAGE_SIZE // 2, 64], train_phase)
        with tf.variable_scope("deconv-layer5"):
            out_5 = deconv_layer(out_4, [5, 5, IMAGE_CHANNEL, 64], [1, 2, 2, 1], [tf.shape(out_4)[0], IMAGE_SIZE, IMAGE_SIZE, IMAGE_CHANNEL], train_phase, has_batch_norm=False)

        # out_1 = tf.matmul(noise, generator_variables_dict["W_1"]) + generator_variables_dict["b_1"]
        # out_1 = tf.reshape(out_1, [-1, IMAGE_SIZE // 16, IMAGE_SIZE // 16, 512])
        # out_1 = batch_norm(out_1, generator_variables_dict["beta_1"], generator_variables_dict["gamma_1"], train_phase, scope="bn_1")
        # out_1 = tf.nn.relu(out_1, name='relu_1')
        # out_2 = tf.nn.conv2d_transpose(out_1, generator_variables_dict["W_2"], output_shape=tf.stack([tf.shape(out_1)[0], IMAGE_SIZE // 8, IMAGE_SIZE // 8, 256]), strides=[1, 2, 2, 1], padding='SAME')
        # out_2 = tf.nn.bias_add(out_2, generator_variables_dict["b_2"])
        # out_2 = batch_norm(out_2, generator_variables_dict["beta_2"], generator_variables_dict["gamma_2"], train_phase, scope="bn_2")
        # out_2 = tf.nn.relu(out_2, name='relu_2')

        # out_3 = tf.nn.conv2d_transpose(out_2, generator_variables_dict["W_3"], output_shape=tf.stack([tf.shape(out_2)[0], IMAGE_SIZE // 4, IMAGE_SIZE // 4, 128]), strides=[1, 2, 2, 1], padding='SAME')
        # out_3 = tf.nn.bias_add(out_3, generator_variables_dict["b_3"])
        # out_3 = batch_norm(out_3, generator_variables_dict["beta_3"], generator_variables_dict["gamma_3"], train_phase, scope="bn_3")
        # out_3 = tf.nn.relu(out_3, name='relu_3')

        # out_4 = tf.nn.conv2d_transpose(out_3, generator_variables_dict["W_4"], output_shape=tf.stack([tf.shape(out_3)[0], IMAGE_SIZE // 2, IMAGE_SIZE // 2, 64]), strides=[1, 2, 2, 1], padding='SAME')
        # out_4 = tf.nn.bias_add(out_4, generator_variables_dict["b_4"])
        # out_4 = batch_norm(out_4, generator_variables_dict["beta_4"], generator_variables_dict["gamma_4"], train_phase, scope="bn_4")
        # out_4 = tf.nn.relu(out_4, name='relu_4')

        # out_5 = tf.nn.conv2d_transpose(out_4, generator_variables_dict["W_5"], output_shape=tf.stack([tf.shape(out_4)[0], IMAGE_SIZE, IMAGE_SIZE, IMAGE_CHANNEL]), strides=[1, 2, 2, 1], padding='SAME')
        # out_5 = tf.nn.bias_add(out_5, generator_variables_dict['b_5'])
        # out_5 = tf.nn.tanh(out_5, name='tanh_5')

        # with tf.variable_scope("fc_2**IMAGE_SIZE"):
        #     weight = tf.get_variable('W', [z_dim, 2 * IMAGE_SIZE * IMAGE_SIZE], initializer=tf.truncated_normal_initializer(stddev=0.02))
        #     bias = tf.get_variable("b", [2 * IMAGE_SIZE * IMAGE_SIZE], initializer=tf.constant_initializer(0))

    return out_5

def get_paramter(kernel_size, output_depth, has_batch_norm=True):
    weight = tf.get_variable("W", kernel_size, initializer=tf.truncated_normal_initializer(stddev=0.002))
    bias = tf.get_variable("b", [output_depth], initializer=tf.constant_initializer(0))
    beta = tf.get_variable('beta', [output_depth], initializer=tf.constant_initializer(0), trainable=has_batch_norm)
    gamma = tf.get_variable('gamma', [output_depth], initializer=tf.random_normal_initializer(mean=1.0, stddev=0.02), trainable=has_batch_norm)
    return weight, bias, beta, gamma

def conv_layer(input, kernel_size, strides_size, train_phase, activate='leaky_relu', has_batch_norm=True):
    if has_batch_norm:
        weight, bias, beta, gamma = get_paramter(kernel_size, kernel_size[3])
    else:
        weight, bias, _, _ = get_paramter(kernel_size, kernel_size[3], False)

    out = tf.nn.conv2d(input, weight, strides=strides_size, padding="SAME")
    out = tf.nn.bias_add(out, bias)
    if has_batch_norm:
        out = batch_norm(out, beta, gamma, train_phase)
    
    if activate == 'relu':
        out = tf.nn.relu(out, name='relu_activate')
    elif activate == 'tanh':
        out = tf.nn.tanh(out, name='tanh_activate')
    else:
        out = tf.maximum(0.2 * out, out, name='leaky_relu_activate')
    return out

def deconv_layer(input, kernel_size, strides_size, output_shape, train_phase, activate='leaky_relu', has_batch_norm=True):
    if has_batch_norm:
        weight, bias, beta, gamma = get_paramter(kernel_size, kernel_size[2])
    else:
        weight, bias, _, _ = get_paramter(kernel_size, kernel_size[2], False)

    out = tf.nn.conv2d_transpose(input, weight, output_shape=tf.stack(output_shape), strides=strides_size, padding="SAME")
    out = tf.nn.bias_add(out, bias)
    
    if has_batch_norm:
        out = batch_norm(out, beta, gamma, train_phase)
    
    if activate == 'relu':
        out = tf.nn.relu(out, name='relu_activate')
    elif activate == 'tanh':
        out = tf.nn.tanh(out, name='tanh_activate')
    else:
        out = tf.maximum(0.2 * out, out, name='leaky_relu_activate')
    return out

def discriminator(input_images):
    with tf.variable_scope("Discriminator"):
        # Encoder
        with tf.variable_scope("conv-layer1"):
            out_1 = conv_layer(input_images, [4, 4, IMAGE_CHANNEL, 32], [1, 2, 2, 1], train_phase)
        with tf.variable_scope("conv-layer2"):
            out_2 = conv_layer(out_1, [4, 4, 32, 64], [1, 2, 2, 1], train_phase)
        with tf.variable_scope("conv-layer3"):
            out_3 = conv_layer(out_2, [4, 4, 64, 128], [1, 2, 2, 1], train_phase)

        encode = tf.reshape(out_3, [-1, 2 * IMAGE_SIZE * IMAGE_SIZE])
        # Decoder
        out_3 = tf.reshape(encode, [-1, IMAGE_SIZE // 8, IMAGE_SIZE // 8, 128])

        with tf.variable_scope("deconv-layer4"):
            out_4 = deconv_layer(out_3, [4, 4, 64, 128], [1, 2, 2, 1], [tf.shape(out_3)[0], IMAGE_SIZE // 4, IMAGE_SIZE // 4, 64], train_phase)
        with tf.variable_scope("deconv-layer5"):
            out_5 = deconv_layer(out_4, [4, 4, 32, 64], [1, 2, 2, 1], [tf.shape(out_4)[0], IMAGE_SIZE // 2, IMAGE_SIZE // 2, 32], train_phase)
        with tf.variable_scope("deconv-layer6"):
            decoded = deconv_layer(out_5, [4, 4, 3, 32], [1, 2, 2, 1], [tf.shape(out_5)[0], IMAGE_SIZE, IMAGE_SIZE, 3], train_phase, has_batch_norm=False)

        return encode, decoded

# mean squared errors
with tf.variable_scope("Loss") as scope:
    _, real_decoded = discriminator(X)
    fake_image = generator(noise)
    real_loss = tf.sqrt(2 * tf.nn.l2_loss(real_decoded - X)) / batch_size
    
    scope.reuse_variables()
    _, fake_decoded = discriminator(fake_image)
    fake_loss = tf.sqrt(2 * tf.nn.l2_loss(fake_decoded - fake_image)) / batch_size

# with tf.variable_scope('real_loss'):
#     _, real_decoded = discriminator(X)
# real_loss = tf.sqrt(2 * tf.nn.l2_loss(real_decoded - X)) / batch_size

# with tf.variable_scope('fake_loss'):
#     fake_image = generator(noise)
#     _, fake_decoded = discriminator(fake_image)
# fake_loss = tf.sqrt(2 * tf.nn.l2_loss(fake_decoded - fake_image)) / batch_size

# loss
margin = 20
D_loss = margin - fake_loss + real_loss
G_loss = fake_loss

def optimizer(loss, d_or_g):
    optim = tf.train.AdamOptimizer(learning_rate=0.001, beta1=0.5)
    var_list = [v for v in tf.trainable_variables() if v.name.startswith(d_or_g)]
    gradient = optim.compute_gradients(loss, var_list=var_list)
    return optim.apply_gradients(gradient)

train_op_G = optimizer(G_loss, 'fake_loss/Generator')
train_op_D = optimizer(D_loss, 'real_loss/Discriminator')

def generate_fake_img(session, step='final'):
    test_nosie = np.random.uniform(-1.0, 1.0, size=(5, z_dim)).astype(np.float32)
    images = session.run(fake_image, feed_dict={noise: test_nosie, train_phase: False})
    for k in range(5):
        image = images[k, :, :, :]
        image += 1
        image *= 127.5
        image = np.clip(image, 0, 255).astype(np.uint8)
        image = np.reshape(image, (IMAGE_SIZE, IMAGE_SIZE, -1))
        if not os.path.isdir('generate_img'):
            os.mkdir('generate_img');
        misc.imsave('./generate_img/fake_image' + str(step) + str(k) + '.jpg', image)

def EB_GAN(train=True):
    with tf.Session() as sess:
        sess.run(tf.global_variables_initializer(), feed_dict={train_phase: True})
        writer = tf.summary.FileWriter('logs/', sess.graph)
        saver = tf.train.Saver()

        ckpt = tf.train.get_checkpoint_state('./model')
        if ckpt != None:
            print(ckpt.model_checkpoint_path)
            saver.restore(sess, ckpt.model_checkpoint_path)
        elif train:
            print("no model")
        elif not train:
            print("no model to generate the fake image")
            return

        if train:
            step = 0
            for i in range(10):
                for j in range(num_batch):
                    batch_noise = np.random.uniform(-1.0, 1.0, size=[batch_size, z_dim]).astype(np.float32)

                    d_loss, _ = sess.run([D_loss, train_op_D], feed_dict={noise: batch_noise, X: get_next_batch(j), train_phase: True})
                    g_loss, _ = sess.run([G_loss, train_op_G], feed_dict={noise: batch_noise, X: get_next_batch(j), train_phase: True})
                    # g_loss, _ = sess.run([G_loss, train_op_G], feed_dict={noise: batch_noise, X: get_next_batch(j), train_phase: True})

                    print(step, d_loss, g_loss)

                    if step % 100 == 0:
                        saver.save(sess, "./model/celeba.model", global_step=step)
                        # if step % 1000 == 0:
                        generate_fake_img(sess, step=step)
                    step += 1
        else:
            generate_fake_img(sess)

if __name__ == '__main__':
    EB_GAN(True)